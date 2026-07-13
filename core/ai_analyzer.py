"""抖音热点雷达 - AI 分析模块"""

import re
import ssl
import httpx
from core.config import Config


class AIAnalyzer:

    def __init__(self):
        self.api_url = Config.AI_GATEWAY_URL
        self.api_key = Config.AI_GATEWAY_KEY
        self.model = Config.AI_MODEL
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._client = httpx.Client(verify=ctx, timeout=60, trust_env=True)

    def _call_ai(self, prompt, max_tokens=800):
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
            raise Exception(f"AI API {resp.status_code}: {resp.text[:200]}")
        return resp.json()["choices"][0]["message"]["content"]

    # ========== 起势视频分析 ==========

    def analyze_trending_video(self, video, hot_comments=None):
        comments_text = ""
        if hot_comments:
            comments_text = "\n".join([f"- {c}" for c in hot_comments[:15]])

        prompt = f"""我女朋友是抖音手工博主（做风琴本、尼泊尔手工本、手账），我在帮她盯热点。

现在这条视频在抖音上涨得很快：
标题：{video.get('title', '')}
作者：{video.get('author_name', '')}
点赞{video.get('like_count', 0)} 评论{video.get('comment_count', 0)} 收藏{video.get('collect_count', 0)} 分享{video.get('share_count', 0)}
{f"热门评论：{chr(10)}{comments_text}" if comments_text else ""}

用大白话帮我分析，像朋友聊天一样：

【这条火在哪】一两句话说清楚
【评论在聊啥】{f"总结评论区大家关心什么" if comments_text else "跳过"}
【怎么蹭】我女朋友做风琴本/尼泊尔手工的，具体怎么关联拍一条
【视频标题】给3个能直接用的标题"""

        try:
            text = self._call_ai(prompt, max_tokens=600)
            return self._parse_video_analysis(text)
        except Exception as e:
            print(f"[ERROR] AI 分析失败: {e}")
            return {"what": "", "comments": "", "how": "", "titles": [], "raw": str(e)}

    def _parse_video_analysis(self, text):
        result = {"what": "", "comments": "", "how": "", "titles": [], "raw": text}
        sections = re.split(r'【(.+?)】', text)
        for i in range(1, len(sections) - 1, 2):
            label = sections[i].strip()
            content = re.sub(r'\*+', '', sections[i + 1]).strip()
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

    def analyze_hot_topics(self, topics):
        topics_text = "\n".join([f"{i+1}. {t.get('title', '')}" for i, t in enumerate(topics[:25])])

        prompt = (
            "我女朋友是抖音博主，她的内容非常垂直：风琴本制作、尼泊尔手工纸制品、手账排版、画画插画。\n\n"
            f"现在的抖音热搜：\n{topics_text}\n\n"
            "请判断：有没有和她的内容直接相关的？\n\n"
            "判断标准（极其严格）：\n"
            "1. 热搜必须直接涉及：手工制作、画画、插画、美术、文具、本子、纸艺、书法、设计风格\n"
            "2. 或者是正在流行的视觉美学风格（波点风、新中式、莫兰迪色等）\n"
            "3. 热搜本身就得是手工/美术圈的话题才算\n\n"
            "以下全部不算相关（即使能沾边）：\n"
            "- 美食烹饪类（拉花、摆盘不算）\n"
            "- 旅行风景类\n"
            "- 宠物类\n"
            "- 影视综艺明星\n"
            "- 新闻事件\n"
            "- 任何需要'把XX画进手账'来强行关联的\n\n"
            "99%的情况下热搜和手工没关系，直接回复一个字：没有\n"
            "只有热搜本身就是手工美术圈话题时才推荐。\n\n"
            "没有相关的回复：没有\n\n"
            "如果真的有（极少），格式：\n"
            "【热搜】xxx\n"
            "【为什么相关】一句话\n"
            "【可以拍】具体内容\n"
            "【标题】一个标题\n"
            "---"
        )

        try:
            text = self._call_ai(prompt, max_tokens=400)
            return self._parse_hot_analysis(text)
        except Exception as e:
            print(f"[ERROR] 热搜分析失败: {e}")
            return {"opportunities": [], "raw": str(e)}

    def _parse_hot_analysis(self, text):
        result = {"opportunities": [], "raw": text}

        # 没找到
        t = text.strip()
        if t == "没有" or len(t) <= 5 or "没有能" in t or "没啥" in t or "找不到" in t or "没有相关" in t:
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
                elif "相关" in label or "关联" in label or "为什么" in label:
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
