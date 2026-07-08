"""测试推送

    python -m scripts.test_notify
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from core.notifier import Notifier


def main():
    print("Testing webhook notification...")

    notifier = Notifier()

    print("  Sending text message...")
    ok = notifier.send_text("Testing - douyin radar connected!")
    print(f"  Text: {'OK' if ok else 'FAILED'}")

    print("  Sending markdown message...")
    ok = notifier.send_markdown("""🔥 <font color="warning">起势预警 (测试)</font>

**尼泊尔手工风琴本制作全过程**
作者: @测试账号

📊 数据概览:
> 播放 12.3w | 点赞 2.1w
> 评论 1.8k | 收藏 5.6k

💡 起势原因:
🚀 发布 3h 已获 2.1w 赞，增速惊人
📈 点赞是该账号均值的 8.6 倍，明显突破

🔗 [查看视频](https://www.douyin.com/video/test)""")
    print(f"  Markdown: {'OK' if ok else 'FAILED'}")

    if ok:
        print("\nDone! Check your WeChat Work group.")
    else:
        print("\nFailed. Check WECOM_WEBHOOK_URL config.")


if __name__ == "__main__":
    main()
