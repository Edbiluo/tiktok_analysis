"""API - 设置管理（Cookie 更新、账号管理）"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import init_db


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
                # 手动添加监控账号
                sec_uid = body.get("sec_uid", "").strip()
                nickname = body.get("nickname", "").strip()
                if not sec_uid:
                    raise ValueError("sec_uid 不能为空")

                conn.execute("""
                    INSERT INTO authors (id, nickname, is_monitored, created_at, updated_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        nickname = COALESCE(excluded.nickname, nickname),
                        is_monitored = 1,
                        updated_at = CURRENT_TIMESTAMP
                """, (sec_uid, nickname or "未命名"))
                conn.commit()
                message = f"已添加: {nickname or sec_uid}"

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
