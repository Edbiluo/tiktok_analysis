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
        """分析热搜，找能蹭的（严格筛选，不硬蹭）"""
        topics_text = "\n".join([f"{i+1}. {t.get('title', '')}" for i, t in enumerate(topics[:25])])

        prompt = f"""我女朋友是抖音手工博主（做风琴本、尼泊尔手工本、手账），我在帮她盯热点。

这是现在的抖音热搜：
{topics_text}

严格筛选规则（必须遵守）：
1. 只挑和"手工制作/手账/本子/纸艺/美学/视觉风格"有天然关联的热搜
2. "天然关联"的意思是：普通观众看到视频标题就觉得合理，而不是"硬拉关系"
3. 灾难新闻、政治、体育比赛、明星八卦 → 绝对不蹭
4. 如果只是把猫/美食/旅行"放在手工本旁边"就算关联 → 这是硬蹭，不算
5. 真的找不到就直接说"今天热搜没有能自然关联手工的"

能蹭的例子：
- "万物皆可波点风" → 做波点主题手账本（风格天然匹配）
- "新中式穿搭" → 做新中式风格手工本（美学相通）
- 某个治愈/解压类话题 → 手工制作过程本身就是治愈内容

不能蹭的例子：
- "台风来了" → 不可能关联
- "猫咪搞笑" → 把猫放本子旁边是硬蹭
- "某明星恋爱" → 强行写情侣手账是硬蹭

如果找到了（最多2个），每个这样写：
【热搜】xxx
【为什么能蹭】一句话，说清楚这个热搜和手工的天然关联点
【拍什么】具体内容，2-3句话
【标题】一个视频标题
---

如果找不到，只写一行：
今天热搜没有能自然关联手工的"""

        try:
            text = self._call_ai(prompt, max_tokens=600)
            return self._parse_hot_analysis(text)
        except Exception as e:
            print(f"[ERROR] 热搜分析失败: {e}")
            return {"opportunities": [], "raw": str(e)}

    def _parse_hot_analysis(self, text: str) -> dict:
        """解析热搜分析"""
        result = {"opportunities": [], "raw": text}

        # 检查是否"没啥能蹭的"
        if "没有能自然关联" in text or "没啥能蹭" in text or "没有合适" in text:
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
