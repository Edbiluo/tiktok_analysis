"""抖音热点雷达 - 数据采集主脚本

用法：
    python -m scripts.collect              # 完整采集（同行 + 热搜）
    python -m scripts.collect --hot-only   # 只采集热搜
    python -m scripts.collect --notify     # 采集完发送通知
"""

import sys
import time
import argparse
from core.douyin import DouyinClient
from core.database import init_db, save_author, save_video, save_snapshot, get_author_avg_stats
from core.analyzer import TrendingAnalyzer
from core.notifier import WeComNotifier


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
        # 保存视频基本信息
        save_video(conn, video)

        # 保存数据快照
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
        # 获取作者历史数据
        author_stats = get_author_avg_stats(conn, video.get("author_id", ""))

        # 分析
        analysis = analyzer.analyze_video(video, author_stats)

        results.append({
            "video": video,
            "analysis": analysis,
        })

    # 按评分排序
    results.sort(key=lambda x: x["analysis"]["score"], reverse=True)
    return results


def run_collection(hot_only: bool = False, notify: bool = True):
    """执行一次完整采集"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始采集...")

    # 初始化
    conn = init_db()
    client = DouyinClient()
    notifier = WeComNotifier()

    all_videos = []
    hot_topics = []

    try:
        # 采集热搜
        print("  📈 采集抖音热搜...")
        hot_topics = collect_hot_search(client, conn)
        print(f"     获取到 {len(hot_topics)} 条热搜")

        if not hot_only:
            # 获取监控列表
            cursor = conn.execute("SELECT id, nickname FROM authors WHERE is_monitored = 1")
            authors = cursor.fetchall()

            if not authors:
                print("  ⚠️  监控列表为空，请先导入关注账号")
                print("     运行: python -m scripts.import_following")
                return

            print(f"  👥 采集 {len(authors)} 个同行账号...")
            for i, (sec_uid, nickname) in enumerate(authors, 1):
                print(f"     [{i}/{len(authors)}] {nickname}...")
                videos = collect_user_videos(client, conn, sec_uid)
                all_videos.extend(videos)
                # 避免请求过快
                time.sleep(2)

            print(f"     共采集 {len(all_videos)} 条视频")

        # 分析
        print("  🧠 分析起势视频...")
        results = analyze_videos(conn, all_videos)
        trending = [r for r in results if r["analysis"]["is_trending"]]
        print(f"     发现 {len(trending)} 条起势视频")

        # 通知
        if notify and trending:
            print("  📤 发送企微通知...")
            for item in trending[:3]:  # 最多推 3 条
                notifier.send_trending_alert(item["video"], item["analysis"])
                time.sleep(1)
            print("     ✅ 通知已发送")

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
