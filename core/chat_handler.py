"""抖音热点雷达 - 群聊 @机器人 交互模块

用户在企微群里 @机器人 提问 → 先回"在想了" → 查数据 + AI 生成口语化回复 → 推回群里。
"""

import re
import ssl
import httpx
from xml.etree import ElementTree
from core.config import Config
from core.notifier import Notifier
from core.database import (
    get_connection, init_db,
    get_top_videos, get_recent_hot_topics, get_system_status,
)


SYSTEM_PROMPT_TEMPLATE = """你是「抖音热点雷达」的 AI 助手，在企业微信群里回答问题。

【你服务的人】
一个做手工的抖音博主（风琴本、尼泊尔手工纸制品、手账排版），你帮她盯同行动态和抖音热点。

【你的风格】
- 像朋友微信聊天一样说话，别太正式
- 可以用 emoji 但别刷屏
- 简洁直接，群聊不适合大段文字
- 有数据就说数据，没有就直说，绝不编造
- 回复控制在 200 字以内

【当前掌握的数据】
{data_context}

【回复规则】
- 问同行/竞品/数据相关：结合上面的真实数据回答
- 问热搜/热点相关：看热搜列表，判断有没有跟手工相关的
- 问系统状态/运行情况：用系统状态数据回答
- 随便聊天/打招呼：简短友好回应
- 问到数据里没有的东西：诚实说"这个我目前没盯到"
- 不要用 markdown 格式（群聊不渲染）
- 不要自称"我是AI"之类的，就正常聊天"""


class ChatHandler:
    """处理企微群聊 @机器人 的消息"""

    def __init__(self):
        self.notifier = Notifier()
        # AI 客户端（独立于 AIAnalyzer，用更短的 timeout）
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._ai_client = httpx.Client(verify=ctx, timeout=8, trust_env=True)

    def handle(self, decrypted_xml: str):
        """处理解密后的消息 XML

        流程：解析 → 去重 → "在想了" → 查数据 → AI → 发回复
        """
        # 1. 解析消息
        msg = self._parse_message_xml(decrypted_xml)
        if not msg:
            return

        # 只处理文本消息
        if msg.get("msg_type") != "text":
            return

        msg_id = msg.get("msg_id", "")
        content = self._strip_at_prefix(msg.get("content", ""))

        if not content.strip():
            self.notifier.send_text("有啥想聊的直接说哈~ 😊")
            return

        # 2. 去重（防企微重试）
        try:
            conn = get_connection()
        except Exception as e:
            print(f"[CHAT] DB 连接失败: {e}")
            self.notifier.send_text("数据库开小差了，等会儿再问我~ 😅")
            return

        try:
            if msg_id and self._is_duplicate(conn, msg_id):
                print(f"[CHAT] 重复消息跳过: {msg_id}")
                return

            # 先记录 MsgId 防重试
            if msg_id:
                self._save_msg_record(conn, msg_id, content)
        except Exception as e:
            print(f"[CHAT] 去重检查异常: {e}")
            # 继续处理，不因去重失败而丢消息

        # 3. 先回一条"在想了"
        self.notifier.send_text("🤔 让我想想...")

        # 4. 查询数据上下文
        try:
            data_context = self._build_data_context(conn)
        except Exception as e:
            print(f"[CHAT] 数据查询异常: {e}")
            data_context = "（数据暂时查不到）"

        # 5. 调用 AI
        try:
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(data_context=data_context)
            reply = self._call_ai_chat(system_prompt, content)
        except Exception as e:
            print(f"[CHAT] AI 调用失败: {e}")
            reply = "AI 想太久了... 稍后再问我试试？😅"

        # 6. 推送回复
        self.notifier.send_text(reply)

        # 更新已发送标记
        try:
            if msg_id:
                conn.execute(
                    "UPDATE alerts SET sent = 1 WHERE video_id = ? AND alert_type = 'chat_reply'",
                    (msg_id,)
                )
                conn.commit()
        except Exception:
            pass

    def _parse_message_xml(self, xml_str: str) -> dict:
        """解析企微消息 XML"""
        try:
            root = ElementTree.fromstring(xml_str)
            return {
                "msg_type": (root.findtext("MsgType") or "").strip(),
                "content": (root.findtext("Content") or "").strip(),
                "msg_id": (root.findtext("MsgId") or "").strip(),
                "from_user": (root.findtext("FromUserName") or "").strip(),
                "to_user": (root.findtext("ToUserName") or "").strip(),
                "create_time": (root.findtext("CreateTime") or "").strip(),
                "agent_id": (root.findtext("AgentID") or "").strip(),
            }
        except Exception as e:
            print(f"[CHAT] XML 解析失败: {e}")
            return None

    def _strip_at_prefix(self, content: str) -> str:
        """去掉消息开头的 @机器人名 前缀"""
        # 企微群聊 @应用 时，Content 格式为 "@应用名 实际内容"
        stripped = re.sub(r'^@\S+\s*', '', content).strip()
        return stripped

    def _is_duplicate(self, conn, msg_id: str) -> bool:
        """检查消息是否已处理过"""
        cursor = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE video_id = ? AND alert_type = 'chat_reply'",
            (msg_id,)
        )
        return cursor.fetchone()[0] > 0

    def _save_msg_record(self, conn, msg_id: str, user_message: str):
        """记录消息 ID（防企微重试重复处理）"""
        conn.execute(
            "INSERT INTO alerts (video_id, alert_type, score, message, sent) VALUES (?, 'chat_reply', 0, ?, 0)",
            (msg_id, user_message[:500])
        )
        conn.commit()

    def _build_data_context(self, conn) -> str:
        """构建注入 AI prompt 的数据上下文"""
        parts = []

        # 同行 TOP5
        top_videos = get_top_videos(conn, limit=5)
        if top_videos:
            lines = []
            for i, v in enumerate(top_videos, 1):
                lines.append(
                    f"{i}. \"{v['title'][:30]}\" @{v['author_name']} | "
                    f"赞{_fmt(v['like_count'])} 评{_fmt(v['comment_count'])} 藏{_fmt(v['collect_count'])}"
                )
            parts.append("--- 同行近期 TOP5 视频 ---\n" + "\n".join(lines))
        else:
            parts.append("--- 同行近期 TOP5 视频 ---\n暂无数据")

        # 热搜 TOP10
        hot_topics = get_recent_hot_topics(conn, limit=10)
        if hot_topics:
            lines = [f"{i}. {t['title']} (热度 {_fmt(t['hot_value'])})" for i, t in enumerate(hot_topics, 1)]
            parts.append("--- 最新热搜 TOP10 ---\n" + "\n".join(lines))
        else:
            parts.append("--- 最新热搜 TOP10 ---\n暂无数据")

        # 系统状态
        status = get_system_status(conn)
        parts.append(
            f"--- 系统状态 ---\n"
            f"监控账号: {status['monitored_authors']} | "
            f"总视频: {status['total_videos']} | "
            f"最近采集: {status['last_snapshot']} | "
            f"近24h预警: {status['recent_alerts']}条"
        )

        return "\n\n".join(parts)

    def _call_ai_chat(self, system_prompt: str, user_message: str) -> str:
        """调用 DeepSeek AI 生成聊天回复"""
        resp = self._ai_client.post(
            f"{Config.AI_GATEWAY_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.AI_GATEWAY_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": Config.AI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 400,
                "temperature": 0.8,
            },
        )
        if resp.status_code != 200:
            raise Exception(f"AI API {resp.status_code}: {resp.text[:200]}")
        return resp.json()["choices"][0]["message"]["content"]

    def close(self):
        self._ai_client.close()


def _fmt(num) -> str:
    """格式化数字（复用 Notifier 的逻辑）"""
    try:
        num = int(num or 0)
    except (TypeError, ValueError):
        return "0"
    if num >= 10000:
        return f"{num/10000:.1f}w"
    elif num >= 1000:
        return f"{num/1000:.1f}k"
    return str(num)
