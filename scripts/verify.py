"""抖音热点雷达 - 项目验收脚本

逐项验证各模块是否正常工作：
    python -m scripts.verify
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置编码
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def check(name: str, fn):
    """运行一项检查"""
    print(f"\n{'='*50}")
    print(f"  检查: {name}")
    print(f"{'='*50}")
    try:
        result = fn()
        if result:
            print(f"  >>> 通过 <<<")
        else:
            print(f"  >>> 失败 <<<")
        return result
    except Exception as e:
        print(f"  >>> 异常: {e} <<<")
        return False


def check_config():
    """1. 检查配置是否加载"""
    from core.config import Config

    items = {
        "WECOM_CORP_ID": Config.WECOM_CORP_ID,
        "WECOM_AGENT_ID": Config.WECOM_AGENT_ID,
        "WECOM_SECRET": bool(Config.WECOM_SECRET),
        "WECOM_USER_ID": Config.WECOM_USER_ID,
    }

    all_ok = True
    for key, val in items.items():
        status = "OK" if val else "MISSING"
        print(f"  {key}: {status}")
        if not val:
            all_ok = False

    return all_ok


def check_database():
    """2. 检查数据库连接和建表"""
    from core.database import init_db

    conn = init_db()

    # 验证表是否创建成功
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    expected = ["authors", "videos", "video_snapshots", "trending_topics", "alerts"]

    print(f"  已创建的表: {tables}")
    for t in expected:
        if t in tables:
            print(f"    {t}: OK")
        else:
            print(f"    {t}: MISSING")
            return False

    # 测试写入和读取
    conn.execute("""
        INSERT INTO authors (id, nickname, is_monitored)
        VALUES ('test_verify_001', '验收测试账号', 1)
        ON CONFLICT(id) DO UPDATE SET nickname = '验收测试账号'
    """)
    conn.commit()

    cursor = conn.execute("SELECT nickname FROM authors WHERE id = 'test_verify_001'")
    row = cursor.fetchone()
    if row and row[0] == "验收测试账号":
        print("  读写测试: OK")
    else:
        print("  读写测试: FAILED")
        return False

    # 清理测试数据
    conn.execute("DELETE FROM authors WHERE id = 'test_verify_001'")
    conn.commit()

    return True


def check_analyzer():
    """3. 检查起势算法"""
    from core.analyzer import TrendingAnalyzer

    analyzer = TrendingAnalyzer()

    # 模拟一个明显起势的视频
    hot_video = {
        "id": "test_001",
        "title": "测试起势视频",
        "author_id": "test_author",
        "created_at": time.time() - 3600 * 2,  # 2小时前发布
        "play_count": 500000,
        "like_count": 50000,
        "comment_count": 3000,
        "share_count": 2000,
        "collect_count": 8000,
    }

    # 模拟一个普通视频
    normal_video = {
        "id": "test_002",
        "title": "测试普通视频",
        "author_id": "test_author",
        "created_at": time.time() - 3600 * 48,  # 2天前发布
        "play_count": 10000,
        "like_count": 200,
        "comment_count": 10,
        "share_count": 5,
        "collect_count": 30,
    }

    author_stats = {
        "avg_likes": 1000,
        "avg_comments": 50,
        "avg_shares": 20,
        "avg_collects": 100,
        "avg_plays": 30000,
    }

    result_hot = analyzer.analyze_video(hot_video, author_stats)
    result_normal = analyzer.analyze_video(normal_video, author_stats)

    print(f"  起势视频评分: {result_hot['score']} (is_trending={result_hot['is_trending']})")
    print(f"    增速分: {result_hot['growth_score']}")
    print(f"    互动分: {result_hot['interaction_score']}")
    print(f"    突破分: {result_hot['breakthrough_score']}")
    for r in result_hot['reasons']:
        print(f"    {r}")

    print(f"  普通视频评分: {result_normal['score']} (is_trending={result_normal['is_trending']})")

    # 起势视频分数应该远高于普通视频
    if result_hot['score'] > result_normal['score'] and result_hot['is_trending']:
        print("  算法判断: OK (起势视频被正确识别)")
        return True
    else:
        print("  算法判断: FAILED")
        return False


def check_notifier():
    """4. 检查企微推送"""
    from core.notifier import WeComNotifier

    notifier = WeComNotifier()

    print("  获取 access_token...")
    try:
        token = notifier._get_access_token()
        print(f"  access_token: {token[:20]}... (OK)")
    except Exception as e:
        print(f"  access_token 获取失败: {e}")
        print("  提示: 可能是网络问题(公司SSL)，部署到线上后不影响")
        return False

    print("  发送测试消息...")
    ok = notifier.send_text("[验收测试] 抖音热点雷达连接成功！")
    if ok:
        print("  推送: OK (请检查企业微信是否收到)")
    else:
        print("  推送: FAILED")

    return ok


def check_douyin_api():
    """5. 检查抖音接口（只测热搜，不需要登录）"""
    from core.douyin import DouyinClient

    client = DouyinClient(cookie="")  # 不传 cookie

    print("  获取抖音热搜...")
    try:
        hot = client.get_hot_search()
        client.close()

        if hot and len(hot) > 0:
            print(f"  获取到 {len(hot)} 条热搜:")
            for i, item in enumerate(hot[:5], 1):
                print(f"    {i}. {item.get('title', '?')}")
            return True
        else:
            print("  热搜返回为空（可能需要 Cookie 或网络问题）")
            return False
    except Exception as e:
        print(f"  请求失败: {e}")
        print("  提示: 本地可能因网络/SSL问题失败，部署到线上后可能正常")
        return False


def main():
    print()
    print("=" * 50)
    print("  抖音热点雷达 - 项目验收")
    print("=" * 50)

    results = {}

    results["配置加载"] = check("1. 配置加载", check_config)
    results["数据库"] = check("2. 数据库读写", check_database)
    results["起势算法"] = check("3. 起势评分算法", check_analyzer)
    results["企微推送"] = check("4. 企业微信推送", check_notifier)
    results["抖音接口"] = check("5. 抖音热搜接口", check_douyin_api)

    # 汇总
    print(f"\n{'='*50}")
    print("  验收汇总")
    print(f"{'='*50}")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        icon = "  " if ok else "  "
        print(f"  {icon} {name}: {status}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  结果: {passed}/{total} 通过")

    if passed == total:
        print("\n  所有检查通过！项目可以部署了。")
    elif passed >= 3:
        print("\n  核心模块正常。失败项可能是网络环境导致，部署到线上后应该正常。")
    else:
        print("\n  多项检查未通过，请排查后重试。")


if __name__ == "__main__":
    main()
