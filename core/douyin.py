"""抖音热点雷达 - 抖音数据采集模块"""

import time
import httpx
from typing import Optional
from core.config import Config


class DouyinClient:
    """抖音数据采集客户端"""

    BASE_URL = "https://www.douyin.com"

    def __init__(self, cookie: str = ""):
        self.cookie = cookie or self._load_cookie()
        self.client = httpx.Client(
            headers=self._build_headers(),
            timeout=30,
            follow_redirects=True,
        )

    @staticmethod
    def _load_cookie() -> str:
        """加载 Cookie：优先从数据库，其次从环境变量"""
        # 先尝试从数据库读
        try:
            from core.database import get_connection
            conn = get_connection()
            cursor = conn.execute("SELECT value FROM settings WHERE key = 'douyin_cookie'")
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass

        # 降级到环境变量
        return Config.DOUYIN_COOKIE

    def _build_headers(self) -> dict:
        """构建请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
        }

    def get_user_videos(self, sec_user_id: str, count: int = 20, max_cursor: int = 0) -> Optional[dict]:
        """
        获取用户视频列表

        Args:
            sec_user_id: 用户的 sec_uid（从主页链接获取）
            count: 获取数量
            max_cursor: 翻页游标
        """
        url = f"{self.BASE_URL}/aweme/v1/web/aweme/post/"
        params = {
            "sec_user_id": sec_user_id,
            "count": count,
            "max_cursor": max_cursor,
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_video_list(data, sec_user_id)
            else:
                print(f"[ERROR] 获取用户视频失败: status={resp.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            return None

    def get_video_detail(self, aweme_id: str) -> Optional[dict]:
        """
        获取单个视频详情

        Args:
            aweme_id: 视频 ID
        """
        url = f"{self.BASE_URL}/aweme/v1/web/aweme/detail/"
        params = {
            "aweme_id": aweme_id,
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_video_detail(data)
            else:
                return None
        except Exception as e:
            print(f"[ERROR] 获取视频详情异常: {e}")
            return None

    def get_user_info(self, sec_user_id: str) -> Optional[dict]:
        """获取用户信息"""
        url = f"{self.BASE_URL}/aweme/v1/web/user/profile/other/"
        params = {
            "sec_user_id": sec_user_id,
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_user_info(data)
            else:
                return None
        except Exception as e:
            print(f"[ERROR] 获取用户信息异常: {e}")
            return None

    def get_hot_search(self) -> Optional[list]:
        """获取抖音热搜榜（不需要登录）"""
        url = f"{self.BASE_URL}/aweme/v1/web/hot/search/list/"
        params = {
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_hot_search(data)
            else:
                return None
        except Exception as e:
            print(f"[ERROR] 获取热搜异常: {e}")
            return None

    def get_following_list(self, sec_user_id: str, count: int = 50, max_time: int = 0) -> Optional[list]:
        """
        获取关注列表（需要登录态）

        Args:
            sec_user_id: 自己账号的 sec_uid
            count: 获取数量
            max_time: 翻页时间戳
        """
        url = f"{self.BASE_URL}/aweme/v1/web/user/following/list/"
        params = {
            "sec_user_id": sec_user_id,
            "count": count,
            "max_time": max_time,
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
        }

        try:
            resp = self.client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_following_list(data)
            else:
                return None
        except Exception as e:
            print(f"[ERROR] 获取关注列表异常: {e}")
            return None

    # ========== 数据解析 ==========

    def _parse_video_list(self, data: dict, sec_user_id: str) -> dict:
        """解析视频列表"""
        result = {
            "videos": [],
            "has_more": data.get("has_more", False),
            "max_cursor": data.get("max_cursor", 0),
        }

        aweme_list = data.get("aweme_list", [])
        for item in aweme_list:
            video = self._extract_video_info(item, sec_user_id)
            if video:
                result["videos"].append(video)

        return result

    def _parse_video_detail(self, data: dict) -> Optional[dict]:
        """解析视频详情"""
        aweme_detail = data.get("aweme_detail")
        if not aweme_detail:
            return None
        return self._extract_video_info(aweme_detail)

    def _extract_video_info(self, item: dict, sec_user_id: str = "") -> Optional[dict]:
        """从原始数据中提取视频信息"""
        try:
            statistics = item.get("statistics", {})
            author = item.get("author", {})

            return {
                "id": item.get("aweme_id", ""),
                "title": item.get("desc", ""),
                "author_id": author.get("sec_uid", sec_user_id),
                "author_name": author.get("nickname", ""),
                "cover_url": item.get("video", {}).get("cover", {}).get("url_list", [""])[0],
                "duration": item.get("video", {}).get("duration", 0),
                "created_at": item.get("create_time", 0),
                # 数据指标
                "play_count": statistics.get("play_count", 0),
                "like_count": statistics.get("digg_count", 0),
                "comment_count": statistics.get("comment_count", 0),
                "share_count": statistics.get("share_count", 0),
                "collect_count": statistics.get("collect_count", 0),
            }
        except Exception:
            return None

    def _parse_user_info(self, data: dict) -> Optional[dict]:
        """解析用户信息"""
        user = data.get("user", {})
        if not user:
            return None

        return {
            "id": user.get("sec_uid", ""),
            "nickname": user.get("nickname", ""),
            "avatar_url": user.get("avatar_larger", {}).get("url_list", [""])[0],
            "follower_count": user.get("follower_count", 0),
            "following_count": user.get("following_count", 0),
            "total_favorited": user.get("total_favorited", 0),
            "video_count": user.get("aweme_count", 0),
            "signature": user.get("signature", ""),
        }

    def _parse_hot_search(self, data: dict) -> list:
        """解析热搜榜"""
        result = []
        word_list = data.get("data", {}).get("word_list", [])
        for item in word_list:
            result.append({
                "title": item.get("word", ""),
                "hot_value": item.get("hot_value", 0),
                "event_time": item.get("event_time", ""),
            })
        return result

    def _parse_following_list(self, data: dict) -> list:
        """解析关注列表"""
        result = []
        followings = data.get("followings", [])
        for user in followings:
            result.append({
                "id": user.get("sec_uid", ""),
                "nickname": user.get("nickname", ""),
                "avatar_url": user.get("avatar_larger", {}).get("url_list", [""])[0],
                "follower_count": user.get("follower_count", 0),
                "video_count": user.get("aweme_count", 0),
            })
        return result

    def close(self):
        """关闭客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
