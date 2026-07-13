"""测试抖音评论接口 + 用Cookie搜索"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.douyin import DouyinClient

client = DouyinClient()

# 测试1：搜索接口（需要Cookie）
print("=== 测试搜索接口 ===")
print(f"Cookie length: {len(client.cookie)}")

if len(client.cookie) > 50:
    url = "https://www.douyin.com/aweme/v1/web/search/item/"
    params = {
        "keyword": "风琴本",
        "count": 5,
        "sort_type": 2,  # 按最多点赞
        "publish_time": 7,  # 最近一周
        "search_channel": "aweme_general",
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
    }
    try:
        resp = client.client.get(url, params=params)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        status_msg = data.get("status_msg", "")
        status_code = data.get("status_code", -1)
        print(f"status_code={status_code}, msg={status_msg}")

        items = data.get("data", [])
        print(f"Results: {len(items)}")
        if items:
            for item in items[:3]:
                aweme = item.get("aweme_info", {})
                if aweme:
                    stats = aweme.get("statistics", {})
                    title = aweme.get("desc", "")[:40]
                    likes = stats.get("digg_count", 0)
                    author = aweme.get("author", {}).get("nickname", "")
                    aweme_id = aweme.get("aweme_id", "")
                    print(f"  - [{aweme_id}] {title}")
                    print(f"    @{author} | likes={likes}")
    except Exception as e:
        print(f"Search error: {e}")
else:
    print("No cookie loaded, skipping search test")

# 测试2：评论接口（用一个已知的视频ID）
print("\n=== 测试评论接口 ===")
# 先从同行视频里取一个ID
from core.database import init_db
conn = init_db()
cursor = conn.execute("SELECT id, title FROM videos LIMIT 1")
row = cursor.fetchone()
if row:
    vid = row[0]
    title = row[1]
    print(f"Testing with video: {vid} ({title[:30]})")

    url = "https://www.douyin.com/aweme/v1/web/comment/list/"
    params = {
        "aweme_id": vid,
        "count": 10,
        "cursor": 0,
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
    }
    try:
        resp = client.client.get(url, params=params)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        comments = data.get("comments", [])
        print(f"Comments: {len(comments)}")
        if comments:
            for c in comments[:5]:
                text = c.get("text", "")[:50]
                likes = c.get("digg_count", 0)
                print(f"  - ({likes} likes) {text}")
        else:
            print(f"Raw: {str(data)[:300]}")
    except Exception as e:
        print(f"Comment error: {e}")
else:
    print("No videos in database")

client.close()
