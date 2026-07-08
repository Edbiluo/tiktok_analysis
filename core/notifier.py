"""抖音热点雷达 - 通知模块（企微群机器人 Webhook）"""

import httpx
from core.config import Config


class Notifier:
    """企微群机器人推送 - 无需IP白名单"""

    def __init__(self):
        self.webhook_url = Config.WECOM_WEBHOOK_URL
        self._client = httpx.Client(verify=False, timeout=15)

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
        """发送起势预警（含 AI 分析）"""
        score = analysis["score"]
        reasons = "\n".join(analysis["reasons"])

        content = f"""🔥 <font color="warning">起势预警</font> (评分: {score}/100)

**{video.get('title', '无标题')}**
作者: {video.get('author_name', '未知')}

📊 数据概览:
> 播放 {self._fmt(video.get('play_count', 0))} | 点赞 {self._fmt(video.get('like_count', 0))}
> 评论 {self._fmt(video.get('comment_count', 0))} | 收藏 {self._fmt(video.get('collect_count', 0))}

💡 起势原因:
{reasons}

🔗 [查看视频](https://www.douyin.com/video/{video.get('id', '')})"""

        self.send_markdown(content)

        # 如果有 AI 分析结果，单独发一条
        if ai_result and ai_result.get("explosion_point"):
            ideas = "\n".join([f"> {i+1}. {idea}" for i, idea in enumerate(ai_result.get("content_ideas", [])[:3])])

            ai_content = f"""🧠 **AI 爆点分析**

🎯 **为什么火:**
{ai_result.get('explosion_point', '')}

{f"💬 **评论区洞察:**\n{ai_result.get('comment_insight', '')}" if ai_result.get('comment_insight') else ""}

🔗 **手工赛道怎么蹭:**
{ai_result.get('handcraft_angle', '')}

📝 **选题建议:**
{ideas}"""

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
