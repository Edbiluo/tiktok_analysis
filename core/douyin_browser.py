"""抖音数据采集 - Playwright 浏览器方式（搜索+评论）

用无头浏览器绕过 a_bogus 签名验证。
浏览器自动生成所有签名参数。
"""

import json
import time
from typing import Optional


class DouyinBrowser:
    """用 Playwright 浏览器采集抖音数据（搜索/评论等需要签名的接口）"""

    def __init__(self, cookie_str: str = ""):
        self.cookie_str = cookie_str or self._load_cookie()
        self._browser = None
        self._page = None
        self._playwright = None

    @staticmethod
    def _load_cookie() -> str:
        try:
            from core.database import get_connection
            conn = get_connection()
            cursor = conn.execute("SELECT value FROM settings WHERE key = 'douyin_cookie'")
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        import os
        return os.environ.get("DOUYIN_COOKIE", "")

    def _ensure_browser(self):
        """懒加载浏览器（只在需要时启动）"""
        if self._page:
            return

        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)

        # 解析 cookie 字符串为 playwright 格式
        cookies = []
        for pair in self.cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".douyin.com",
                    "path": "/",
                })

        context = self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        if cookies:
            context.add_cookies(cookies)

        self._page = context.new_page()
        # 先访问抖音首页让 cookie 生效
        self._page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)

    def search_videos(self, keyword: str, count: int = 20, sort_type: int = 0) -> list:
        """
        搜索视频（通过浏览器，自动处理签名）

        sort_type: 0=综合, 1=最新, 2=最多点赞
        """
        self._ensure_browser()

        videos = []
        try:
            # 拦截搜索 API 的响应
            search_data = []

            def handle_response(response):
                if "/aweme/v1/web/search/item/" in response.url:
                    try:
                        data = response.json()
                        items = data.get("data", [])
                        if not items:
                            items = data.get("aweme_list", [])
                        for item in items:
                            aweme = item.get("aweme_info", item)
                            if aweme and aweme.get("aweme_id"):
                                search_data.append(aweme)
                    except Exception:
                        pass

            self._page.on("response", handle_response)

            # 构造搜索 URL
            search_url = f"https://www.douyin.com/search/{keyword}?type=video"
            if sort_type == 1:
                search_url += "&sort_type=1"
            elif sort_type == 2:
                search_url += "&sort_type=2"

            self._page.goto(search_url, wait_until="networkidle", timeout=20000)
            time.sleep(3)  # 等待搜索结果加载

            # 解析结果
            for aweme in search_data[:count]:
                video = self._extract_video(aweme)
                if video:
                    videos.append(video)

            self._page.remove_listener("response", handle_response)

        except Exception as e:
            print(f"[ERROR] 浏览器搜索失败 '{keyword}': {e}")

        return videos

    def get_video_comments(self, aweme_id: str, count: int = 20) -> list:
        """获取视频热门评论"""
        self._ensure_browser()

        comments = []
        try:
            comment_data = []

            def handle_response(response):
                if "/aweme/v1/web/comment/list/" in response.url:
                    try:
                        data = response.json()
                        for c in data.get("comments", []):
                            comment_data.append({
                                "text": c.get("text", ""),
                                "likes": c.get("digg_count", 0),
                                "reply_count": c.get("reply_comment_total", 0),
                            })
                    except Exception:
                        pass

            self._page.on("response", handle_response)

            # 访问视频页面（会自动加载评论）
            video_url = f"https://www.douyin.com/video/{aweme_id}"
            self._page.goto(video_url, wait_until="networkidle", timeout=20000)
            time.sleep(3)

            # 按点赞数排序
            comments = sorted(comment_data, key=lambda x: x["likes"], reverse=True)[:count]

            self._page.remove_listener("response", handle_response)

        except Exception as e:
            print(f"[ERROR] 获取评论失败 '{aweme_id}': {e}")

        return comments

    def _extract_video(self, aweme: dict) -> Optional[dict]:
        """从原始数据提取视频信息"""
        try:
            stats = aweme.get("statistics", {})
            author = aweme.get("author", {})
            return {
                "id": aweme.get("aweme_id", ""),
                "title": aweme.get("desc", ""),
                "author_id": author.get("sec_uid", ""),
                "author_name": author.get("nickname", ""),
                "follower_count": author.get("follower_count", 0),
                "cover_url": aweme.get("video", {}).get("cover", {}).get("url_list", [""])[0],
                "duration": aweme.get("video", {}).get("duration", 0),
                "created_at": aweme.get("create_time", 0),
                "play_count": stats.get("play_count", 0),
                "like_count": stats.get("digg_count", 0),
                "comment_count": stats.get("comment_count", 0),
                "share_count": stats.get("share_count", 0),
                "collect_count": stats.get("collect_count", 0),
                "source": "keyword_search",
            }
        except Exception:
            return None

    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
