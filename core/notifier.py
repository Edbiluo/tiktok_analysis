"""抖音热点雷达 - 通知模块（企微群机器人 Webhook）"""

import ssl
import time
import httpx
from core.config import Config


class Notifier:
    """企微群机器人推送"""

    def __init__(self):
        self.webhook_url = Config.WECOM_WEBHOOK_URL
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._client = httpx.Client(verify=ctx, timeout=15, trust_env=True)

    def _send(self, payload: dict) -> bool:
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
        return self._send({"msgtype": "text", "text": {"content": content}})

    def send_markdown(self, content: str) -> bool:
        return self._send({"msgtype": "markdown", "markdown": {"content": content}})

    def send_trending_alert(self, video: dict, analysis: dict, ai_result: dict = None) -> bool:
        """发送起势预警 + AI 分析"""
        score = analysis["score"]
        reasons = "\n".join(analysis["reasons"])

        # 第一条：数据
        content = f"""🔥 <font color="warning">起势预警</font> ({score}分)

**{video.get('title', '无标题')}**
@{video.get('author_name', '未知')}

> 赞 {self._fmt(video.get('like_count', 0))} | 评 {self._fmt(video.get('comment_count', 0))} | 藏 {self._fmt(video.get('collect_count', 0))}

{reasons}
🔗 [查看视频](https://www.douyin.com/video/{video.get('id', '')})"""

        self.send_markdown(content)

        # 第二条：AI 分析
        if ai_result and ai_result.get("how"):
            titles = "\n".join([f"> {t}" for t in ai_result.get("titles", [])[:3]])

            ai_content = f"""💡 **怎么蹭** | {video.get('title', '')[:15]}

🔥 {ai_result.get('what', '')}
{f"💬 {ai_result.get('comments', '')}" if ai_result.get('comments') else ""}

👉 **具体做法:** {ai_result.get('how', '')}

📝 **标题参考:**
{titles}"""

            time.sleep(2)
            return self.send_markdown(ai_content)

        return True

    def send_hot_opportunities(self, analysis_result: dict) -> bool:
        """推送热搜蹭热度机会"""
        opportunities = analysis_result.get("opportunities", [])
        if not opportunities:
            return False

        sections = []
        for i, opp in enumerate(opportunities[:3], 1):
            section = f"""{i}. 🔍 **{opp.get('topic', '')}**
> {opp.get('angle', '')}
> 拍什么: {opp.get('shoot', '')}
> 标题: {opp.get('title', '')}
"""
            sections.append(section)

        content = f"""📈 <font color="info">热搜蹭热度机会</font>

{"".join(sections)}"""

        return self.send_markdown(content)

    @staticmethod
    def _fmt(num: int) -> str:
        if num >= 10000:
            return f"{num/10000:.1f}w"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        return str(num)
