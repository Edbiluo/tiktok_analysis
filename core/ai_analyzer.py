"""抖音热点雷达 - AI 爆点分析模块"""

import os
import ssl
import httpx
from core.config import Config


class AIAnalyzer:
    """用 LLM 分析视频爆点并给出手工赛道蹭热度建议"""

    def __init__(self):
        self.api_url = Config.AI_GATEWAY_URL
        self.api_key = Config.AI_GATEWAY_KEY
        self.model = Config.AI_MODEL
        # 创建不验证 SSL 的上下文 + 信任环境代理
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._client = httpx.Client(verify=ctx, timeout=60, trust_env=True)

    def analyze_trending_video(self, video: dict, hot_comments: list = None) -> dict:
        """
        分析一条起势视频的爆点 + 给出手工赛道蹭热度建议

        Returns:
            {
                "explosion_point": "爆点分析...",
                "comment_insight": "评论区洞察...",
                "handcraft_angle": "手工赛道关联建议...",
                "content_ideas": ["具体选题1", "具体选题2", ...],
                "raw_response": "完整AI回复",
            }
        """
        comments_text = ""
        if hot_comments:
            top_comments = hot_comments[:15]
            comments_text = "\n".join([f"- {c}" for c in top_comments])

        prompt = f"""你是一个抖音内容运营专家，同时熟悉手工类赛道（风琴本、尼泊尔手工艺品、手账本、手作）。

现在有一条抖音视频正在起势（数据增长异常快），请分析：

## 视频信息
- 标题：{video.get('title', '无标题')}
- 作者：{video.get('author_name', '未知')}
- 播放：{video.get('play_count', 0)}
- 点赞：{video.get('like_count', 0)}
- 评论：{video.get('comment_count', 0)}
- 收藏：{video.get('collect_count', 0)}
- 分享：{video.get('share_count', 0)}

{f"## 热门评论\n{comments_text}" if comments_text else ""}

请按以下格式回答（每部分 2-3 句话，简洁有力）：

### 1. 爆点分析
这条视频为什么火？核心吸引力是什么？（从选题、情绪、形式、节奏等角度）

### 2. 评论区洞察
{"评论区在讨论什么？用户的关注点和情绪是什么？" if comments_text else "（无评论数据，跳过）"}

### 3. 手工赛道怎么蹭
作为风琴本/尼泊尔手工赛道的博主，如何借这个热点做内容？给出具体的关联角度。

### 4. 具体选题建议
给出 3 个可以直接拍的视频选题（标题+简要内容描述），要能蹭到这个热点又和手工相关。"""

        try:
            resp = self._client.post(
                f"{self.api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_response(content)

        except Exception as e:
            print(f"[ERROR] AI 分析失败: {e}")
            return {
                "explosion_point": "AI 分析失败",
                "comment_insight": "",
                "handcraft_angle": "",
                "content_ideas": [],
                "raw_response": str(e),
            }

    def _parse_response(self, text: str) -> dict:
        """解析 AI 回复，提取各部分"""
        result = {
            "explosion_point": "",
            "comment_insight": "",
            "handcraft_angle": "",
            "content_ideas": [],
            "raw_response": text,
        }

        sections = text.split("###")
        for section in sections:
            section = section.strip()
            lower = section.lower()
            content = "\n".join(section.split("\n")[1:]).strip()

            if "爆点" in section[:20]:
                result["explosion_point"] = content
            elif "评论" in section[:20]:
                result["comment_insight"] = content
            elif "蹭" in section[:20] or "手工" in section[:20]:
                result["handcraft_angle"] = content
            elif "选题" in section[:20]:
                result["content_ideas"] = [
                    line.strip().lstrip("0123456789.、- ")
                    for line in content.split("\n")
                    if line.strip() and len(line.strip()) > 5
                ]

        return result

    def close(self):
        self._client.close()
