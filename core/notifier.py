"""抖音热点雷达 - 企业微信通知模块"""

import httpx
import ssl
import time
from core.config import Config


class WeComNotifier:
    """企业微信消息推送"""

    TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

    def __init__(self):
        self.corp_id = Config.WECOM_CORP_ID
        self.agent_id = Config.WECOM_AGENT_ID
        self.secret = Config.WECOM_SECRET
        self.user_id = Config.WECOM_USER_ID
        self._access_token = ""
        self._token_expires_at = 0
        # 兼容公司网络 SSL 中间人证书
        self._client = httpx.Client(verify=False, timeout=15)

    def _get_access_token(self) -> str:
        """获取 access_token（有 2 小时有效期，自动缓存）"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        resp = self._client.get(self.TOKEN_URL, params={
            "corpid": self.corp_id,
            "corpsecret": self.secret,
        })
        data = resp.json()

        if data.get("errcode") == 0:
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
            return self._access_token
        else:
            raise Exception(f"获取 access_token 失败: {data}")

    def send_text(self, content: str, to_user: str = "") -> bool:
        """发送文本消息"""
        token = self._get_access_token()
        payload = {
            "touser": to_user or self.user_id,
            "msgtype": "text",
            "agentid": int(self.agent_id),
            "text": {"content": content},
        }

        resp = self._client.post(f"{self.SEND_URL}?access_token={token}", json=payload)
        data = resp.json()
        success = data.get("errcode") == 0
        if not success:
            print(f"[ERROR] 企微推送失败: {data}")
        return success

    def send_markdown(self, content: str, to_user: str = "") -> bool:
        """发送 Markdown 消息（企业微信支持简单 Markdown）"""
        token = self._get_access_token()
        payload = {
            "touser": to_user or self.user_id,
            "msgtype": "markdown",
            "agentid": int(self.agent_id),
            "markdown": {"content": content},
        }

        resp = self._client.post(f"{self.SEND_URL}?access_token={token}", json=payload)
        data = resp.json()
        success = data.get("errcode") == 0
        if not success:
            print(f"[ERROR] 企微推送失败: {data}")
        return success

    def send_trending_alert(self, video: dict, analysis: dict) -> bool:
        """
        发送起势预警

        Args:
            video: 视频信息
            analysis: 分析结果
        """
        score = analysis["score"]
        reasons = "\n".join(analysis["reasons"])

        content = f"""🔥 **起势预警** (评分: {score}/100)

**{video.get('title', '无标题')}**
作者: {video.get('author_name', '未知')}

📊 数据概览:
> 播放 {self._format_num(video.get('play_count', 0))} | 点赞 {self._format_num(video.get('like_count', 0))}
> 评论 {self._format_num(video.get('comment_count', 0))} | 收藏 {self._format_num(video.get('collect_count', 0))}

💡 起势原因:
{reasons}

🔗 [查看视频](https://www.douyin.com/video/{video.get('id', '')})"""

        return self.send_markdown(content)

    def send_daily_report(self, trending_videos: list, hot_topics: list) -> bool:
        """发送每日汇总报告"""
        video_section = ""
        for i, item in enumerate(trending_videos[:5], 1):
            v = item["video"]
            a = item["analysis"]
            video_section += f"\n{i}. **{v.get('title', '')[:20]}** (评分{a['score']})\n   @{v.get('author_name', '')} | 赞{self._format_num(v.get('like_count', 0))}"

        topic_section = ""
        for topic in hot_topics[:5]:
            topic_section += f"\n- {topic.get('title', '')} ({self._format_num(topic.get('hot_value', 0))}热度)"

        content = f"""📊 **抖音雷达日报**

**🔥 起势视频 TOP5:**
{video_section or '暂无起势视频'}

**📈 相关热搜:**
{topic_section or '暂无相关热搜'}

[查看详情](https://douyin-radar.vercel.app)"""

        return self.send_markdown(content)

    @staticmethod
    def _format_num(num: int) -> str:
        """格式化数字"""
        if num >= 10000:
            return f"{num/10000:.1f}w"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        return str(num)
