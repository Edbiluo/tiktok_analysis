"""抖音热点雷达 - AI 分析模块（说人话版）"""

import re
import ssl
import httpx
from core.config import Config


class AIAnalyzer:
    """用 AI 分析热点，给出接地气的蹭热度建议"""

    def __init__(self):
        self.api_url = Config.AI_GATEWAY_URL
        self.api_key = Config.AI_GATEWAY_KEY
        self.model = Config.AI_MODEL
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._client = httpx.Client(verify=ctx, timeout=60, trust_env=True)

    def _call_ai(self, prompt: str, max_tokens: int = 800) -> str:
        """调用 AI 接口"""
        resp = self._client.post(
            f"{self.api_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            raise Exception(f"AI API 返回 {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ========== 起势视频分析 ==========

    def analyze_trending_video(self, video: dict, hot_comments: list = None) -> dict:
        """分析一条起势视频，说人话"""
        comments_text = ""
        if hot_comments:
            comments_text = "\n".join([f"- {c}" for c in hot_comments[:15]])

        prompt = f"""我女朋友是抖音手工博主（做风琴本、尼泊尔手工本、手账），我在帮她盯热点。

现在这条视频在抖音上涨得很快：
标题：{video.get('title', '')}
作者：{video.get('author_name', '')}
点赞{video.get('like_count', 0)} 评论{video.get('comment_count', 0)} 收藏{video.get('collect_count', 0)} 分享{video.get('share_count', 0)}
{f"热门评论：\n{comments_text}" if comments_text else ""}

用大白话帮我分析，别用"赋能""矩阵""打法"这种词，像朋友聊天一样：

【这条火在哪】一两句话说清楚（什么内容，为什么吸引人）
【评论在聊啥】{f"总结评论区大家关心什么" if comments_text else "跳过"}
【怎么蹭】我女朋友做风琴本/尼泊尔手工的，具体怎么关联这个热点拍一条，说清楚拍什么
【视频标题】给3个能直接用的标题"""

        try:
            text = self._call_ai(prompt, max_tokens=600)
            return self._parse_video_analysis(text)
        except Exception as e:
            print(f"[ERROR] AI 分析失败: {e}")
            return {"what": "", "comments": "", "how": "", "titles": [], "raw": str(e)}

    def _parse_video_analysis(self, text: str) -> dict:
        """解析视频分析"""
        result = {"what": "", "comments": "", "how": "", "titles": [], "raw": text}

        sections = re.split(r'【(.+?)】', text)
        # sections 是 [前文, 标签1, 内容1, 标签2, 内容2, ...]
        for i in range(1, len(sections) - 1, 2):
            label = sections[i].strip()
            content = sections[i + 1].strip()
            # 去掉 markdown 格式
            content = re.sub(r'\*+', '', content).strip()

            if "火" in label or "这条" in label:
                result["what"] = content[:200]
            elif "评论" in label or "聊" in label:
                result["comments"] = content[:200]
            elif "蹭" in label or "怎么" in label:
                result["how"] = content[:300]
            elif "标题" in label:
                result["titles"] = [
                    re.sub(r'^[\d.、\-\s]+', '', line).strip()
                    for line in content.split("\n")
                    if line.strip() and len(line.strip()) > 5
                ][:3]

        return result

    # ========== 热搜分析 ==========

    def analyze_hot_topics(self, topics: list) -> dict:
        """分析热搜，找能蹭的"""
        topics_text = "\n".join([f"{i+1}. {t.get('title', '')}" for i, t in enumerate(topics[:25])])

        prompt = f"""我女朋友是抖音手工博主（做风琴本、尼泊尔手工本、手账），我在帮她盯热点。

这是现在的抖音热搜：
{topics_text}

帮我挑出 2-3 个最能和"手工/手账/风琴本/手作"关联的热点。

要求：
- 不是所有热搜都能蹭，挑不出来就说"今天没啥能蹭的"
- 情绪类（治愈、解压、浪漫）和生活方式类最容易关联
- 用大白话说，像朋友微信聊天

每个热点这样写：
【热搜】xxx
【怎么关联】一句话说清楚
【拍什么】具体拍什么内容，说清楚
【标题】一个能直接用的视频标题
---"""

        try:
            text = self._call_ai(prompt, max_tokens=800)
            return self._parse_hot_analysis(text)
        except Exception as e:
            print(f"[ERROR] 热搜分析失败: {e}")
            return {"opportunities": [], "raw": str(e)}

    def _parse_hot_analysis(self, text: str) -> dict:
        """解析热搜分析"""
        result = {"opportunities": [], "raw": text}

        # 检查是否"没啥能蹭的"
        if "没啥能蹭" in text or "没有合适" in text:
            return result

        blocks = re.split(r'---+', text)
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            opp = {}
            sections = re.split(r'【(.+?)】', block)
            for i in range(1, len(sections) - 1, 2):
                label = sections[i].strip()
                content = re.sub(r'\*+', '', sections[i + 1]).strip()

                if "热搜" in label:
                    opp["topic"] = content.split("\n")[0].strip()
                elif "关联" in label:
                    opp["angle"] = content.split("\n")[0].strip()
                elif "拍" in label:
                    opp["shoot"] = content[:150]
                elif "标题" in label:
                    opp["title"] = content.split("\n")[0].strip()

            if opp.get("topic"):
                result["opportunities"].append(opp)

        return result

    def close(self):
        self._client.close()
