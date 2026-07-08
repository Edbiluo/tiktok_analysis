"""API - 设置管理（Cookie 更新、账号管理）"""

import json
import re
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import init_db


def extract_sec_uid(text):
    """从各种格式的输入中提取 sec_uid"""
    text = text.strip()
    # 匹配 https://www.douyin.com/user/xxx 格式
    match = re.search(r'user/([A-Za-z0-9_-]+)', text)
    if match:
        return match.group(1)
    # 如果本身就是 sec_uid（一般是 MS4w 开头的长字符串）
    if len(text) > 20 and not text.startswith('http'):
        return text
    return text


def fetch_user_info(sec_uid, cookie):
    """用抖音 API 获取用户基本信息"""
    try:
        from core.douyin import DouyinClient
        client = DouyinClient(cookie=cookie)
        info = client.get_user_info(sec_uid)
        client.close()
        return info
    except Exception as e:
        print(f"[WARN] 获取用户信息失败: {e}")
        return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """获取当前设置"""
        try:
            conn = init_db()

            # 创建设置表（如果不存在）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            # 获取 Cookie 状态（不返回完整值，只返回是否有值和更新时间）
            cursor = conn.execute(
                "SELECT key, LENGTH(value) as len, updated_at FROM settings WHERE key = 'douyin_cookie'"
            )
            row = cursor.fetchone()

            cookie_status = {
                "has_cookie": row is not None and row[1] > 0,
                "cookie_length": row[1] if row else 0,
                "updated_at": row[2] if row else None,
            }

            # 获取监控账号数量
            cursor = conn.execute("SELECT COUNT(*) FROM authors WHERE is_monitored = 1")
            author_count = cursor.fetchone()[0]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "data": {
                    "cookie_status": cookie_status,
                    "monitored_count": author_count,
                }
            }, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_POST(self):
        """更新设置"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            action = body.get("action", "")
            conn = init_db()

            # 确保设置表存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            if action == "update_cookie":
                # 更新 Cookie
                cookie = body.get("cookie", "").strip()
                if not cookie:
                    raise ValueError("Cookie 不能为空")

                conn.execute("""
                    INSERT INTO settings (key, value, updated_at)
                    VALUES ('douyin_cookie', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                """, (cookie,))
                conn.commit()
                message = "Cookie 已更新"

            elif action == "add_author":
                # 添加监控账号（支持批量，换行分隔）
                raw_input = body.get("sec_uid", "").strip()
                if not raw_input:
                    raise ValueError("请输入抖音主页链接或 sec_uid")

                # 支持换行、逗号、空格分隔的多个链接
                items = re.split(r'[\n,]+', raw_input)
                items = [item.strip() for item in items if item.strip()]

                if not items:
                    raise ValueError("未识别到有效链接")

                # 获取 Cookie（用于拉取用户信息）
                cursor = conn.execute("SELECT value FROM settings WHERE key = 'douyin_cookie'")
                row = cursor.fetchone()
                cookie = row[0] if row else ""

                added = []
                failed = []

                for item in items:
                    sec_uid = extract_sec_uid(item)
                    if not sec_uid:
                        failed.append(item)
                        continue

                    # 尝试获取用户信息
                    nickname = ""
                    follower_count = 0
                    avatar_url = ""
                    video_count = 0

                    if cookie:
                        info = fetch_user_info(sec_uid, cookie)
                        if info:
                            nickname = info.get("nickname", "")
                            follower_count = info.get("follower_count", 0)
                            avatar_url = info.get("avatar_url", "")
                            video_count = info.get("video_count", 0)

                    conn.execute("""
                        INSERT INTO authors (id, nickname, avatar_url, follower_count, video_count, is_monitored, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            nickname = CASE WHEN excluded.nickname != '' THEN excluded.nickname ELSE authors.nickname END,
                            avatar_url = CASE WHEN excluded.avatar_url != '' THEN excluded.avatar_url ELSE authors.avatar_url END,
                            follower_count = CASE WHEN excluded.follower_count > 0 THEN excluded.follower_count ELSE authors.follower_count END,
                            video_count = CASE WHEN excluded.video_count > 0 THEN excluded.video_count ELSE authors.video_count END,
                            is_monitored = 1,
                            updated_at = CURRENT_TIMESTAMP
                    """, (sec_uid, nickname, avatar_url, follower_count, video_count))
                    added.append(nickname or sec_uid[:20])

                conn.commit()

                if added and not failed:
                    message = f"已添加 {len(added)} 个账号: {', '.join(added)}"
                elif added and failed:
                    message = f"已添加 {len(added)} 个，{len(failed)} 个失败"
                else:
                    raise ValueError("全部添加失败，请检查链接格式")

            elif action == "remove_author":
                # 移除监控账号
                author_id = body.get("author_id", "")
                conn.execute("UPDATE authors SET is_monitored = 0 WHERE id = ?", (author_id,))
                conn.commit()
                message = "已移除"

            else:
                raise ValueError(f"未知操作: {action}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "message": message}, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
