"""测试抖音搜索接口 - 多种参数组合"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.douyin import DouyinClient

client = DouyinClient()
print(f"Cookie length: {len(client.cookie)}")

# 测试多种搜索参数组合
tests = [
    {"keyword": "手工", "sort_type": 0, "publish_time": 0, "desc": "手工+综合+不限时间"},
    {"keyword": "手工", "sort_type": 2, "publish_time": 0, "desc": "手工+最多点赞+不限"},
    {"keyword": "手账", "sort_type": 0, "publish_time": 7, "desc": "手账+综合+一周内"},
    {"keyword": "风琴本", "sort_type": 0, "publish_time": 0, "desc": "风琴本+综合+不限"},
]

for t in tests:
    print(f"\n=== {t['desc']} ===")
    url = "https://www.douyin.com/aweme/v1/web/search/item/"
    params = {
        "keyword": t["keyword"],
        "count": 10,
        "offset": 0,
        "sort_type": t["sort_type"],
        "publish_time": t["publish_time"],
        "search_channel": "aweme_general",
        "search_source": "normal_search",
        "query_correct_type": 1,
        "is_filter_search": 0,
        "from_group_id": "",
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
        "pc_client_type": 1,
    }
    try:
        resp = client.client.get(url, params=params)
        data = resp.json()
        sc = data.get("status_code", -1)
        msg = data.get("status_msg", "")
        items = data.get("data", [])
        has_more = data.get("has_more", False)
        print(f"  status_code={sc}, msg={msg}, results={len(items)}, has_more={has_more}")

        if items:
            for item in items[:2]:
                aweme = item.get("aweme_info", {})
                if aweme:
                    stats = aweme.get("statistics", {})
                    print(f"  - {aweme.get('desc', '')[:40]}")
                    print(f"    likes={stats.get('digg_count',0)}")
        elif not items:
            # 打印所有返回的key看看结构
            print(f"  All keys: {list(data.keys())}")
            # 看看有没有别的数据字段
            for k, v in data.items():
                if k not in ("log_pb",) and v:
                    vstr = str(v)[:100]
                    print(f"  {k}: {vstr}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(2)

# 测试另一个搜索路径
print("\n=== 测试 general search 路径 ===")
url2 = "https://www.douyin.com/aweme/v1/web/general/search/single/"
params2 = {
    "keyword": "手工",
    "count": 10,
    "offset": 0,
    "search_channel": "aweme_general",
    "search_source": "normal_search",
    "aid": "6383",
    "cookie_enabled": "true",
    "platform": "PC",
}
try:
    resp = client.client.get(url2, params=params2)
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    sc = data.get("status_code", -1)
    items = data.get("data", [])
    print(f"  status_code={sc}, results={len(items)}")
    if items:
        for item in items[:2]:
            aweme = item.get("aweme_info", {})
            if aweme:
                print(f"  - {aweme.get('desc', '')[:40]}")
    else:
        print(f"  Keys: {list(data.keys())}")
except Exception as e:
    print(f"  Error: {e}")

# 测试评论接口（换一种请求方式）
print("\n=== 测试评论接口 v2 ===")
from core.database import init_db
conn = init_db()
cursor = conn.execute("""
    SELECT v.id, v.title FROM videos v
    JOIN video_snapshots vs ON v.id = vs.video_id
    WHERE vs.like_count > 100
    ORDER BY vs.like_count DESC LIMIT 3
""")
rows = cursor.fetchall()
for row in rows:
    vid, title = row[0], row[1][:30]
    print(f"\nVideo: {vid} ({title})")

    url = "https://www.douyin.com/aweme/v1/web/comment/list/"
    params = {
        "aweme_id": vid,
        "count": 5,
        "cursor": 0,
        "item_type": 0,
        "insert_ids": "",
        "rcFT": "",
        "aid": "6383",
        "cookie_enabled": "true",
        "platform": "PC",
    }
    try:
        resp = client.client.get(url, params=params)
        print(f"  Status: {resp.status_code}")
        if resp.text:
            data = resp.json()
            comments = data.get("comments", [])
            total = data.get("total", 0)
            print(f"  Total comments: {total}, Got: {len(comments)}")
            if comments:
                for c in comments[:3]:
                    text = c.get("text", "")[:50]
                    likes = c.get("digg_count", 0)
                    print(f"    ({likes} likes) {text}")
            else:
                print(f"  Keys: {list(data.keys())}")
                sc = data.get("status_code", -1)
                print(f"  status_code={sc}, msg={data.get('status_msg','')}")
        else:
            print("  Empty response")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1)

client.close()
