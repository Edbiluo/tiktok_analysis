"""抖音热点雷达 - 配置模块"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """应用配置"""

    # 企业微信
    WECOM_CORP_ID = os.getenv("WECOM_CORP_ID", "")
    WECOM_AGENT_ID = os.getenv("WECOM_AGENT_ID", "")
    WECOM_SECRET = os.getenv("WECOM_SECRET", "")
    WECOM_USER_ID = os.getenv("WECOM_USER_ID", "XuXingXin")
    WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL", "")

    # AI 分析（DeepSeek）
    AI_GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "https://api.deepseek.com")
    AI_GATEWAY_KEY = os.getenv("AI_GATEWAY_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "deepseek-chat")

    # 抖音
    DOUYIN_COOKIE = os.getenv("DOUYIN_COOKIE", "")

    # 数据库
    TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
    TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

    # 采集配置
    MONITOR_INTERVAL_HOURS = int(os.getenv("MONITOR_INTERVAL_HOURS", "4"))
    TRENDING_THRESHOLD = float(os.getenv("TRENDING_THRESHOLD", "2.5"))

    # 起势评分权重
    SCORE_WEIGHTS = {
        "growth_rate": 0.35,      # 增速分权重
        "interaction": 0.35,      # 互动质量权重
        "breakthrough": 0.30,     # 账号突破权重
    }

    # 互动率基准（手工类赛道的经验值）
    BASELINE = {
        "like_rate": 0.03,        # 点赞率基准 3%
        "comment_rate": 0.005,    # 评论率基准 0.5%
        "share_rate": 0.002,      # 分享率基准 0.2%
        "collect_rate": 0.01,     # 收藏率基准 1%（手工类偏高）
    }
