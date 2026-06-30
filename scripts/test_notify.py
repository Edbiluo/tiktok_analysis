"""测试企业微信推送

直接运行验证推送是否正常：
    python -m scripts.test_notify
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.notifier import WeComNotifier


def main():
    print("🧪 测试企业微信推送...")
    print(f"   Corp ID: {os.getenv('WECOM_CORP_ID', '未设置')[:8]}...")
    print(f"   Agent ID: {os.getenv('WECOM_AGENT_ID', '未设置')}")
    print(f"   User ID: {os.getenv('WECOM_USER_ID', '未设置')}")
    print()

    notifier = WeComNotifier()

    # 先发简单文本
    print("   发送文本消息...")
    ok = notifier.send_text("🧪 抖音热点雷达 - 推送测试成功！")
    if ok:
        print("   ✅ 文本消息发送成功！")
    else:
        print("   ❌ 文本消息发送失败")
        return

    # 再发 Markdown
    print("   发送 Markdown 消息...")
    ok = notifier.send_markdown("""🔥 **起势预警 (测试)**

**尼泊尔手工风琴本制作全过程**
作者: @测试账号

📊 数据概览:
> 播放 12.3w | 点赞 2.1w
> 评论 1.8k | 收藏 5.6k

💡 起势原因:
🚀 发布 3h 已获 2.1w 赞，增速惊人
📈 点赞是该账号均值的 8.6 倍，明显突破

🔗 [查看视频](https://www.douyin.com/video/test)""")

    if ok:
        print("   ✅ Markdown 消息发送成功！")
        print("\n🎉 全部测试通过！请检查企业微信是否收到了两条消息。")
    else:
        print("   ❌ Markdown 消息发送失败")


if __name__ == "__main__":
    main()
