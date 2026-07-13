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

        # 热搜 AI 分析（核心高频功能，每次热搜有变化就分析）
        if notify and hot_topics and Config.AI_GATEWAY_KEY:
            # 取当前热搜前10的标题，和上次对比
            current_top = set(t.get('title', '') for t in hot_topics[:10])
            cursor = conn.execute("""
                SELECT message FROM alerts
                WHERE alert_type = 'hot_analysis'
                ORDER BY created_at DESC LIMIT 1
            """)
            last_row = cursor.fetchone()
            last_topics = last_row[0] if last_row else ""

            # 前10热搜有1个以上变化就重新分析（热搜变化快，要及时）
            if last_topics:
                old_set = set(last_topics.split("|"))
                new_count = len(current_top - old_set)
                should_analyze = new_count >= 1
            else:
                should_analyze = True

            if should_analyze:
                print("  🧠 AI 分析热搜蹭热度机会...")
                try:
                    ai = AIAnalyzer()
                    hot_analysis = ai.analyze_hot_topics(hot_topics)
                    opps = hot_analysis.get("opportunities", [])
                    if opps:
                        print(f"     发现 {len(opps)} 个蹭热度机会，推送中...")
                        notifier.send_hot_opportunities(hot_analysis)
                    else:
                        print("     今天热搜没有能自然关联手工的")
                    # 保存本次分析的热搜词（用于下次去重）
                    save_alert(conn, "hot_search", "hot_analysis", 0,
                               "|".join(current_top))
                    ai.close()
                except Exception as e:
                    print(f"     热搜 AI 分析失败: {e}")
            else:
                print("  ℹ️  最近 1 小时已分析过热搜，跳过")

        if not hot_only:
            # 同行采集降频：检查最近 2 小时是否已采集过
            cursor = conn.execute("""
                SELECT COUNT(*) FROM video_snapshots
                WHERE snapshot_at > datetime('now', '-2 hours')
            """)
            recent_snapshots = cursor.fetchone()[0]

            if recent_snapshots > 10:
                print("  ℹ️  最近 2 小时已采集过同行，跳过")
            else:
                # Cookie 有效性检测
                check_cookie_valid(client, conn, notifier)

                # 获取监控列表
                cursor = conn.execute("SELECT id, nickname FROM authors WHERE is_monitored = 1")
                authors = cursor.fetchall()

                if not authors:
                    print("  ⚠️  监控列表为空，请先导入关注账号")
                else:
                    print(f"  👥 采集 {len(authors)} 个同行账号...")
                    for i, (sec_uid, nickname) in enumerate(authors, 1):
                        print(f"     [{i}/{len(authors)}] {nickname}...")
                        videos = collect_user_videos(client, conn, sec_uid)
                        all_videos.extend(videos)
                        time.sleep(2)

                    print(f"     共采集 {len(all_videos)} 条视频")

        # 分析
        print("  🧠 分析起势视频...")
        results = analyze_videos(conn, all_videos)
        trending = [r for r in results if r["analysis"]["is_trending"]]

        # 按等级分组
        explosive = [r for r in trending if r["analysis"]["level"] == "explosive"]
        rising = [r for r in trending if r["analysis"]["level"] == "trending"]
        potential = [r for r in trending if r["analysis"]["level"] == "potential"]

        print(f"     🔥🔥🔥 爆款: {len(explosive)} | 🔥🔥 起势: {len(rising)} | 🔥 潜力: {len(potential)}")

        # 通知（防重复）
        if notify and trending:
            new_alerts = []
            for item in trending:
                vid = item["video"]["id"]
                if not is_already_alerted(conn, vid):
                    new_alerts.append(item)

            if new_alerts:
                ai = None
                if Config.AI_GATEWAY_KEY:
                    ai = AIAnalyzer()

                print(f"  📤 发送 {len(new_alerts)} 条新预警...")
                for item in new_alerts[:8]:
                    level = item["analysis"]["level"]
                    ai_result = None

                    # 只对爆款和起势做 AI 分析（省 token）
                    if ai and level in ("explosive", "trending"):
                        try:
                            ai_result = ai.analyze_trending_video(item["video"])
                            print(f"     AI 分析完成: {item['video'].get('title', '')[:20]}")
                        except Exception as e:
                            print(f"     AI 分析失败: {e}")

                    notifier.send_trending_alert(item["video"], item["analysis"], ai_result)
                    save_alert(conn, item["video"]["id"], level,
                               item["analysis"]["score"], item["video"].get("title", ""))
                    time.sleep(1)

                if ai:
                    ai.close()
                print("     ✅ 通知已发送")
            else:
                print("  ℹ️  起势视频均已推送过，无新增")

        # 同行 TOP10 + 热搜排行（每天上午10点推一次）
        if notify and not hot_only:
            import datetime
            beijing_hour = (datetime.datetime.utcnow().hour + 8) % 24

            cursor = conn.execute("""
                SELECT COUNT(*) FROM alerts
                WHERE alert_type = 'daily_morning'
                AND created_at > datetime('now', '-20 hours')
            """)
            already_sent = cursor.fetchone()[0]

            # 北京时间 9-11 点之间，且今天没发过
            if 9 <= beijing_hour <= 11 and already_sent == 0:
                print("  📊 生成每日早报（同行TOP10 + 热搜）...")
                cursor = conn.execute("""
                    SELECT v.id, v.title, v.author_id, v.created_at,
                           a.nickname as author_name,
                           vs.like_count, vs.comment_count, vs.collect_count, vs.share_count, vs.play_count
                    FROM videos v
                    JOIN authors a ON v.author_id = a.id
                    JOIN video_snapshots vs ON v.id = vs.video_id
                    WHERE a.is_monitored = 1
                    AND v.created_at > strftime('%s', 'now', '-15 days')
                    AND vs.id IN (SELECT MAX(id) FROM video_snapshots GROUP BY video_id)
                    ORDER BY vs.like_count DESC
                    LIMIT 10
                """)
                top_rows = cursor.fetchall()
                top_videos = [{
                    "id": r[0], "title": r[1], "author_id": r[2], "created_at": r[3],
                    "author_name": r[4], "like_count": r[5], "comment_count": r[6],
                    "collect_count": r[7], "share_count": r[8], "play_count": r[9],
                } for r in top_rows] if top_rows else []

                notifier.send_morning_report(top_videos, hot_topics)
                save_alert(conn, "morning", "daily_morning", 0, "每日早报")
                print("     ✅ 每日早报已推送")

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
