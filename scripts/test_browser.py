"""测试 Playwright 浏览器采集"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.douyin_browser import DouyinBrowser

print("=== Playwright 搜索测试 ===")
with DouyinBrowser() as browser:
    # 测试搜索
    print("\n搜索「风琴本」...")
    videos = browser.search_videos("风琴本", count=5, sort_type=2)
    print(f"找到 {len(videos)} 条视频")
    for v in videos[:3]:
        print(f"  - {v['title'][:40]}")
        print(f"    @{v['author_name']} | 赞{v['like_count']} | 评{v['comment_count']}")
        print(f"    ID: {v['id']}")

    # 测试评论
    if videos:
        vid = videos[0]["id"]
        print(f"\n获取视频 {vid} 的评论...")
        comments = browser.get_video_comments(vid, count=10)
        print(f"获取到 {len(comments)} 条评论")
        for c in comments[:5]:
            print(f"  ({c['likes']}赞) {c['text'][:50]}")

print("\n=== 测试完成 ===")
