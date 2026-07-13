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
        """分析热搜，严格筛选和手工/画画有天然关联的"""
        topics_text = "\n".join([f"{i+1}. {t.get('title', '')}" for i, t in enumerate(topics[:25])])

        prompt = f"""我女朋友是抖音博主，做的内容是：
- 风琴本（accordion book，一种可以折叠翻开的手工本子）
- 尼泊尔手工纸制品（用尼泊尔进口手工纸做的本子、信封等）
- 手账（手写日记、手帐排版、贴纸拼贴）
- 她也会画画，可以蹭画画/插画/美术相关的热点

现在的抖音热搜：
{topics_text}

你的任务：从里面找有没有和她的内容有天然关联的热搜。

什么叫"天然关联"（必须满足）：
- 热搜本身和手工/画画/美学/纸艺/文具有直接关系
- 或者热搜是某种视觉风格流行（波点、新中式、莫兰迪色等）
- 或者热搜是某个画画/插画/美术相关的话题
- 观众看到视频标题会觉得"这个博主拍这个很合理"

什么不算（绝对不推）：
- 新闻事件（台风、地震、政治）
- 明星八卦、体育赛事
- 把不相关的东西"放在本子旁边"就算关联
- 任何需要"强行解释为什么相关"的

大部分时候热搜和手工没关系，这很正常。
找不到就回复：没有

如果找到了（最多2个），格式：
【热搜】xxx
【为什么相关】一句大白话
【可以拍】具体说拍什么
【标题】一个标题
---"""

        try:
            text = self._call_ai(prompt, max_tokens=500)
            return self._parse_hot_analysis(text)
        except Exception as e:
            print(f"[ERROR] 热搜分析失败: {e}")
            return {"opportunities": [], "raw": str(e)}

    def _parse_hot_analysis(self, text: str) -> dict:
        """解析热搜分析"""
        result = {"opportunities": [], "raw": text}

        # 检查是否没有找到
        text_lower = text.strip()
        if text_lower == "没有" or "没有能" in text or "没啥能蹭" in text or "没有合适" in text or "找不到" in text:
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
                elif "关联" in label or "为什么" in label or "能蹭" in label:
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
