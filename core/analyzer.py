"""抖音热点雷达 - 起势评分算法"""

import time
from typing import Optional
from core.config import Config
from core.database import get_author_avg_stats


class TrendingAnalyzer:
    """起势分析器 - 判断视频是否有爆发潜力"""

    def __init__(self, conn=None):
        self.conn = conn
        self.weights = Config.SCORE_WEIGHTS
        self.baseline = Config.BASELINE
        self.threshold = Config.TRENDING_THRESHOLD

    def analyze_video(self, video: dict, author_stats: Optional[dict] = None) -> dict:
        """
        综合分析视频是否起势

        Args:
            video: 视频数据 dict（包含 play_count, like_count 等）
            author_stats: 该作者的历史平均数据（可选，从 DB 获取）

        Returns:
            {
                "score": 总分 (0-100),
                "is_trending": 是否起势,
                "growth_score": 增速分,
                "interaction_score": 互动质量分,
                "breakthrough_score": 账号突破分,
                "reasons": ["原因1", "原因2"],
            }
        """
        growth_score = self._calc_growth_score(video)
        interaction_score = self._calc_interaction_score(video)
        breakthrough_score = self._calc_breakthrough_score(video, author_stats)

        # 加权总分
        total_score = (
            self.weights["growth_rate"] * growth_score +
            self.weights["interaction"] * interaction_score +
            self.weights["breakthrough"] * breakthrough_score
        )

        # 判断是否起势
        is_trending = total_score >= self.threshold * 20  # 阈值转换为百分制

        # 生成原因说明
        reasons = self._generate_reasons(video, growth_score, interaction_score, breakthrough_score, author_stats)

        return {
            "score": round(total_score, 1),
            "is_trending": is_trending,
            "growth_score": round(growth_score, 1),
            "interaction_score": round(interaction_score, 1),
            "breakthrough_score": round(breakthrough_score, 1),
            "reasons": reasons,
        }

    def _calc_growth_score(self, video: dict) -> float:
        """
        计算增速分 (0-100)

        核心逻辑：单位时间内的互动增长速度
        """
        created_at = video.get("created_at", 0)
        if not created_at:
            return 0

        # 计算视频已发布的小时数
        hours_since_publish = (time.time() - created_at) / 3600
        if hours_since_publish <= 0:
            hours_since_publish = 0.5  # 防止除零

        like_count = video.get("like_count", 0)
        play_count = video.get("play_count", 0)

        # 每小时点赞增速
        likes_per_hour = like_count / hours_since_publish

        # 根据发布时间段评分（越新越重要）
        time_factor = 1.0
        if hours_since_publish <= 6:
            time_factor = 2.0   # 6小时内，双倍权重
        elif hours_since_publish <= 24:
            time_factor = 1.5   # 24小时内
        elif hours_since_publish <= 72:
            time_factor = 1.0   # 3天内
        else:
            time_factor = 0.5   # 超过3天，降权

        # 增速评分（参考基准：手工类 500赞/小时 算优秀）
        speed_score = min(100, (likes_per_hour / 500) * 100 * time_factor)

        return speed_score

    def _calc_interaction_score(self, video: dict) -> float:
        """
        计算互动质量分 (0-100)

        综合点赞率、评论率、收藏率、分享率
        """
        play_count = video.get("play_count", 0)
        if play_count <= 0:
            return 0

        like_count = video.get("like_count", 0)
        comment_count = video.get("comment_count", 0)
        share_count = video.get("share_count", 0)
        collect_count = video.get("collect_count", 0)

        # 各项互动率
        like_rate = like_count / play_count
        comment_rate = comment_count / play_count
        share_rate = share_count / play_count
        collect_rate = collect_count / play_count

        # 与基准对比得分（超过基准越多分越高）
        like_score = min(100, (like_rate / self.baseline["like_rate"]) * 50)
        comment_score = min(100, (comment_rate / self.baseline["comment_rate"]) * 50)
        share_score = min(100, (share_rate / self.baseline["share_rate"]) * 50)
        collect_score = min(100, (collect_rate / self.baseline["collect_rate"]) * 50)

        # 手工类收藏权重更高
        total = (
            like_score * 0.25 +
            comment_score * 0.25 +
            share_score * 0.20 +
            collect_score * 0.30  # 收藏率对手工类更重要
        )

        return total

    def _calc_breakthrough_score(self, video: dict, author_stats: Optional[dict] = None) -> float:
        """
        计算账号突破分 (0-100)

        这条视频数据是否远超该账号历史平均
        """
        if not author_stats:
            # 如果有数据库连接，尝试从 DB 获取
            if self.conn and video.get("author_id"):
                author_stats = get_author_avg_stats(self.conn, video["author_id"])
            if not author_stats:
                return 50  # 无历史数据时给中间分

        avg_likes = author_stats.get("avg_likes", 0)
        if avg_likes <= 0:
            return 50

        # 计算倍率
        like_ratio = video.get("like_count", 0) / avg_likes

        # 倍率评分：3倍起步，10倍满分
        if like_ratio >= 10:
            score = 100
        elif like_ratio >= 5:
            score = 70 + (like_ratio - 5) * 6
        elif like_ratio >= 3:
            score = 40 + (like_ratio - 3) * 15
        elif like_ratio >= 2:
            score = 20 + (like_ratio - 2) * 20
        else:
            score = like_ratio * 10

        # 小粉丝量加分（粉丝少但数据好，说明内容强）
        follower_count = video.get("follower_count", 0)
        if 0 < follower_count < 10000 and like_ratio >= 3:
            score = min(100, score * 1.3)  # 万粉以下加 30% 权重

        return min(100, score)

    def _generate_reasons(self, video: dict, growth_score: float,
                          interaction_score: float, breakthrough_score: float,
                          author_stats: Optional[dict] = None) -> list:
        """生成人可读的起势原因"""
        reasons = []

        # 增速原因
        if growth_score >= 60:
            created_at = video.get("created_at", 0)
            hours = (time.time() - created_at) / 3600 if created_at else 0
            likes = video.get("like_count", 0)
            reasons.append(f"🚀 发布 {hours:.0f}h 已获 {self._format_num(likes)} 赞，增速惊人")

        # 互动质量原因
        play_count = video.get("play_count", 0)
        if play_count > 0:
            like_rate = video.get("like_count", 0) / play_count
            collect_rate = video.get("collect_count", 0) / play_count
            if like_rate > self.baseline["like_rate"] * 2:
                reasons.append(f"❤️ 点赞率 {like_rate*100:.1f}%，远超平均")
            if collect_rate > self.baseline["collect_rate"] * 2:
                reasons.append(f"⭐ 收藏率 {collect_rate*100:.1f}%，内容价值高")

        # 突破原因
        if breakthrough_score >= 60 and author_stats:
            avg_likes = author_stats.get("avg_likes", 0)
            if avg_likes > 0:
                ratio = video.get("like_count", 0) / avg_likes
                reasons.append(f"📈 点赞是该账号均值的 {ratio:.1f} 倍，明显突破")

        if not reasons:
            reasons.append("📊 综合指标表现良好")

        return reasons

    @staticmethod
    def _format_num(num: int) -> str:
        """格式化数字：10000 → 1w"""
        if num >= 10000:
            return f"{num/10000:.1f}w"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        return str(num)
