"""抖音热点雷达 - 数据采集主脚本

用法：
    python -m scripts.collect              # 完整采集（同行 + 热搜）
    python -m scripts.collect --hot-only   # 只采集热搜
    python -m scripts.collect --no-notify  # 不发送通知
"""

import sys
import time
import argparse
from core.douyin import DouyinClient
from core.database import init_db, save_author, save_video, save_snapshot, get_author_avg_stats
from core.analyzer import TrendingAnalyzer
from core.notifier import Notifier
from core.ai_analyzer import AIAnalyzer
from core.config import Config


def collect_user_videos(client: DouyinClient, conn, sec_user_id: str) -> list:
    """采集单个用户的最新视频"""
    videos = []

    # 获取用户信息
    user_info = client.get_user_info(sec_user_id)
    if user_info:
        save_author(conn, user_info)

    # 获取最新视频
    result = client.get_user_videos(sec_user_id, count=10)
    if not result:
        return videos

    for video in result["videos"]:
        save_video(conn, video)
        save_snapshot(conn, {
            "video_id": video["id"],
            "play_count": video.get("play_count", 0),
            "like_count": video.get("like_count", 0),
            "comment_count": video.get("comment_count", 0),
            "share_count": video.get("share_count", 0),
            "collect_count": video.get("collect_count", 0),
        })
        videos.append(video)

    return videos


def collect_hot_search(client: DouyinClient, conn) -> list:
    """采集热搜"""
    hot_list = client.get_hot_search()
    if not hot_list:
        return []

    for item in hot_list:
        conn.execute("""
            INSERT INTO trending_topics (title, hot_value, snapshot_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (item["title"], item.get("hot_value", 0)))

    conn.commit()
    return hot_list


def analyze_videos(conn, videos: list) -> list:
    """分析所有采集到的视频"""
    analyzer = TrendingAnalyzer(conn)
    results = []

    for video in videos:
        author_stats = get_author_avg_stats(conn, video.get("author_id", ""))
        analysis = analyzer.analyze_video(video, author_stats)
        results.append({
            "video": video,
            "analysis": analysis,
        })

    results.sort(key=lambda x: x["analysis"]["score"], reverse=True)
    return results


def is_already_alerted(conn, video_id: str) -> bool:
    """检查该视频是否已经推送过"""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE video_id = ? AND sent = 1",
        (video_id,)
    )
    return cursor.fetchone()[0] > 0


def save_alert(conn, video_id: str, alert_type: str, score: float, message: str):
    """保存推送记录"""
    conn.execute("""
        INSERT INTO alerts (video_id, alert_type, score, message, sent)
        VALUES (?, ?, ?, ?, 1)
    """, (video_id, alert_type, score, message))
    conn.commit()


def check_cookie_valid(client: DouyinClient, conn, notifier: Notifier):
    """检测 Cookie 是否失效，失效则推送提醒"""
    # 尝试获取一个用户的视频，如果返回空可能是 Cookie 问题
    cursor = conn.execute("SELECT id, nickname FROM authors WHERE is_monitored = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return  # 没有监控账号，跳过检测

    result = client.get_user_videos(row[0], count=1)
    if result is None:
        # 检查是否最近已经提醒过（24小时内）
        cursor = conn.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE alert_type = 'cookie_expired'
            AND created_at > datetime('now', '-24 hours')
        """)
        already_warned = cursor.fetchone()[0] > 0

        if not already_warned:
            notifier.send_text("⚠️ 抖音 Cookie 可能已失效，同行数据无法采集。\n\n请打开仪表盘设置页更新 Cookie：\nhttps://tiktok-analysis-lime.vercel.app")
            save_alert(conn, "cookie", "cookie_expired", 0, "Cookie 失效提醒")
            print("  ⚠️  Cookie 可能失效，已发送提醒")


def run_collection(hot_only: bool = False, notify: bool = True):
    """执行一次完整采集"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始采集...")

    conn = init_db()
    client = DouyinClient()
    notifier = Notifier()

    all_videos = []
    hot_topics = []

    try:
        # 采集热搜
        print("  📈 采集抖音热搜...")
        hot_topics = collect_hot_search(client, conn)
        print(f"     获取到 {len(hot_topics)} 条热搜")

        # 热搜 AI 分析（找蹭热度机会）
        if notify and hot_topics and Config.AI_GATEWAY_KEY:
            # 防重复：检查最近 1 小时是否已经分析过热搜
            cursor = conn.execute("""
                SELECT COUNT(*) FROM alerts
                WHERE alert_type = 'hot_analysis'
                AND created_at > datetime('now', '-1 hours')
            """)
            recent_hot = cursor.fetchone()[0]

            if recent_hot == 0:
                print("  🧠 AI 分析热搜蹭热度机会...")
                try:
                    ai = AIAnalyzer()
                    hot_analysis = ai.analyze_hot_topics(hot_topics)
                    opps = hot_analysis.get("opportunities", [])
                    if opps:
                        print(f"     发现 {len(opps)} 个蹭热度机会，推送中...")
                        notifier.send_hot_opportunities(hot_analysis)
                        save_alert(conn, "hot_search", "hot_analysis", 0,
                                   f"热搜分析: {len(opps)} 个机会")
                    else:
                        print("     今天没啥能蹭的热点")
                    ai.close()
                except Exception as e:
                    print(f"     热搜 AI 分析失败: {e}")
            else:
                print("  ℹ️  最近 1 小时已分析过热搜，跳过")

        if not hot_only:
            # Cookie 有效性检测
            check_cookie_valid(client, conn, notifier)

            # 获取监控列表
            cursor = conn.execute("SELECT id, nickname FROM authors WHERE is_monitored = 1")
            authors = cursor.fetchall()

            if not authors:
                print("  ⚠️  监控列表为空，请先导入关注账号")
                return

            print(f"  👥 采集 {len(authors)} 个同行账号...")
            for i, (sec_uid, nickname) in enumerate(authors, 1):
                print(f"     [{i}/{len(authors)}] {nickname}...")
                videos = collect_user_videos(client, conn, sec_uid)
                all_videos.extend(videos)
                time.sleep(2)  # 避免请求过快

            print(f"     共采集 {len(all_videos)} 条视频")

        # 分析
        print("  🧠 分析起势视频...")
        results = analyze_videos(conn, all_videos)
        trending = [r for r in results if r["analysis"]["is_trending"]]
        print(f"     发现 {len(trending)} 条起势视频")

        # 通知（防重复：只推没推过的）
        if notify and trending:
            new_alerts = []
            for item in trending:
                vid = item["video"]["id"]
                if not is_already_alerted(conn, vid):
                    new_alerts.append(item)

            if new_alerts:
                # AI 分析（只分析前 3 条，省 token）
                ai = None
                if Config.AI_GATEWAY_KEY:
                    ai = AIAnalyzer()
                    print(f"  🧠 AI 分析 {min(len(new_alerts), 3)} 条起势视频...")

                print(f"  📤 发送 {len(new_alerts)} 条新预警...")
                for item in new_alerts[:5]:
                    ai_result = None
                    if ai and new_alerts.index(item) < 3:
                        try:
                            ai_result = ai.analyze_trending_video(item["video"])
                            print(f"     AI 分析完成: {item['video'].get('title', '')[:20]}")
                        except Exception as e:
                            print(f"     AI 分析失败: {e}")

                    notifier.send_trending_alert(item["video"], item["analysis"], ai_result)
                    save_alert(conn, item["video"]["id"], "trending",
                               item["analysis"]["score"], item["video"].get("title", ""))
                    time.sleep(1)

                if ai:
                    ai.close()
                print("     ✅ 通知已发送")
            else:
                print("  ℹ️  起势视频均已推送过，无新增")

        # 输出报告
        print("\n" + "=" * 50)
        print("📊 采集报告")
        print("=" * 50)

        if trending:
            print(f"\n🔥 起势视频 TOP5:")
            for i, item in enumerate(trending[:5], 1):
                v = item["video"]
                a = item["analysis"]
                print(f"  {i}. [{a['score']:.0f}分] {v.get('title', '')[:30]}")
                print(f"     @{v.get('author_name', '')} | "
                      f"赞{v.get('like_count', 0)} | "
                      f"评{v.get('comment_count', 0)} | "
                      f"藏{v.get('collect_count', 0)}")
                for reason in a["reasons"]:
                    print(f"     {reason}")
                print()
        else:
            print("\n  暂无起势视频")

        if hot_topics:
            print(f"\n📈 热搜 TOP10:")
            for i, topic in enumerate(hot_topics[:10], 1):
                print(f"  {i}. {topic['title']} (热度 {topic.get('hot_value', 0)})")

    finally:
        client.close()

    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 采集完成 ✅")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抖音热点雷达 - 数据采集")
    parser.add_argument("--hot-only", action="store_true", help="只采集热搜")
    parser.add_argument("--no-notify", action="store_true", help="不发送通知")
    args = parser.parse_args()

    run_collection(
        hot_only=args.hot_only,
        notify=not args.no_notify,
    )
