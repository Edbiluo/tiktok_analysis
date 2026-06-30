"""抖音热点雷达 - 导入关注列表

首次使用时运行，从你的抖音关注列表导入同行账号到数据库。
需要登录态 Cookie。

用法：
    python -m scripts.import_following --sec-uid YOUR_SEC_UID
"""

import argparse
import time
from core.douyin import DouyinClient
from core.database import init_db, save_author


def import_following(sec_user_id: str):
    """从关注列表导入账号"""
    print(f"正在获取关注列表...")

    conn = init_db()
    client = DouyinClient()

    all_users = []
    max_time = 0

    try:
        while True:
            users = client.get_following_list(sec_user_id, count=50, max_time=max_time)
            if not users:
                break

            all_users.extend(users)
            print(f"  已获取 {len(all_users)} 个账号...")

            if len(users) < 50:
                break  # 没有更多了

            # 简单翻页（实际需要从返回数据中拿 max_time）
            max_time = int(time.time()) - len(all_users) * 86400
            time.sleep(2)

    finally:
        client.close()

    # 保存到数据库
    print(f"\n共获取 {len(all_users)} 个关注账号，正在保存...")
    for user in all_users:
        save_author(conn, user)

    print(f"✅ 已导入 {len(all_users)} 个账号到监控列表")
    print("\n导入的账号:")
    for i, user in enumerate(all_users, 1):
        print(f"  {i}. {user.get('nickname', '未知')} (粉丝: {user.get('follower_count', 0)})")


def import_manual(sec_user_ids: list):
    """手动导入指定账号"""
    print(f"正在导入 {len(sec_user_ids)} 个账号...")

    conn = init_db()
    client = DouyinClient()

    try:
        for sec_uid in sec_user_ids:
            user_info = client.get_user_info(sec_uid)
            if user_info:
                save_author(conn, user_info)
                print(f"  ✅ {user_info.get('nickname', sec_uid)}")
            else:
                print(f"  ❌ 获取失败: {sec_uid}")
            time.sleep(1)
    finally:
        client.close()

    print(f"\n✅ 导入完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入关注列表")
    parser.add_argument("--sec-uid", type=str, help="你的抖音账号 sec_uid")
    parser.add_argument("--manual", nargs="+", help="手动指定 sec_uid 列表")
    args = parser.parse_args()

    if args.manual:
        import_manual(args.manual)
    elif args.sec_uid:
        import_following(args.sec_uid)
    else:
        print("请指定 --sec-uid 或 --manual 参数")
        print("  获取 sec_uid：打开抖音网页版 → 进入你的主页 → URL 中的 user/xxx 部分")
