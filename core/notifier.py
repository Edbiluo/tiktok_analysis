"""抖音热点雷达 - 通知模块（企微群机器人 Webhook）"""

import ssl
import httpx
from core.config import Config


class Notifier:
    """企微群机器人推送 - 无需IP白名单"""

    def __init__(self):
        self.webhook_url = Config.WECOM_WEBHOOK_URL
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._client = httpx.Client(verify=ctx, timeout=15, trust_env=True)

    def _send(self, payload: dict) -> bool:
        """发送消息到群机器人"""
        if not self.webhook_url:
            print("[ERROR] WECOM_WEBHOOK_URL 未配置")
            return False

        try:
            resp = self._client.post(self.webhook_url, json=payload)
            data = resp.json()
            success = data.get("errcode") == 0
            if not success:
                print(f"[ERROR] 推送失败: {data}")
            return success
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            return False

    def send_text(self, content: str) -> bool:
        """发送文本消息"""
        return self._send({
            "msgtype": "text",
            "text": {"content": content},
        })

    def send_markdown(self, content: str) -> bool:
        """发送 Markdown 消息"""
        return self._send({
            "msgtype": "markdown",
            "markdown": {"content": content},
        })

    def send_trending_alert(self, video: dict, analysis: dict, ai_result: dict = None) -> bool:
        """发送起势预警 + AI 分析（拆成两条，间隔发送避免截断）"""
        score = analysis["score"]
        reasons = "\n".join(analysis["reasons"])

        # 第一条：数据预警
        content = f"""🔥 <font color="warning">起势预警</font> (评分: {score}/100)

**{video.get('title', '无标题')}**
作者: {video.get('author_name', '未知')}

📊 数据:
> 播放 {self._fmt(video.get('play_count', 0))} | 赞 {self._fmt(video.get('like_count', 0))} | 评 {self._fmt(video.get('comment_count', 0))} | 藏 {self._fmt(video.get('collect_count', 0))}

{reasons}

🔗 [查看视频](https://www.douyin.com/video/{video.get('id', '')})"""

        self.send_markdown(content)

        # 第二条：AI 分析（精简版，控制在 4096 字节内）
        if ai_result and ai_result.get("explosion_point") and "分析失败" not in ai_result.get("explosion_point", ""):
            ideas = "\n".join([f"{i+1}. {idea[:50]}" for i, idea in enumerate(ai_result.get("content_ideas", [])[:3])])

            explosion = ai_result.get('explosion_point', '')[:200]
            angle = ai_result.get('handcraft_angle', '')[:200]

            ai_content = f"""🧠 **AI 分析** | {video.get('title', '')[:15]}

🎯 **爆点:** {explosion}

🔗 **手工怎么蹭:** {angle}

📝 **选题:**
{ideas}"""

            import time
            time.sleep(2)  # 间隔 2 秒避免被吞
            return self.send_markdown(ai_content)

        return True

    def send_daily_report(self, trending_videos: list, hot_topics: list) -> bool:
        """发送每日汇总报告"""
        video_section = ""
        for i, item in enumerate(trending_videos[:5], 1):
            v = item["video"]
            a = item["analysis"]
            video_section += f"\n{i}. **{v.get('title', '')[:20]}** (评分{a['score']})\n   @{v.get('author_name', '')} | 赞{self._fmt(v.get('like_count', 0))}"

        topic_section = ""
        for topic in hot_topics[:5]:
            topic_section += f"\n- {topic.get('title', '')} ({self._fmt(topic.get('hot_value', 0))}热度)"

        content = f"""📊 **抖音雷达日报**

**🔥 起势视频 TOP5:**
{video_section or '暂无起势视频'}

**📈 相关热搜:**
{topic_section or '暂无相关热搜'}

[查看详情](https://tiktok-analysis-lime.vercel.app)"""

        return self.send_markdown(content)

    @staticmethod
    def _fmt(num: int) -> str:
        if num >= 10000:
            return f"{num/10000:.1f}w"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        return str(num)
