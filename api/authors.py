"""API - 监控账号管理"""

import json
from http.server import BaseHTTPRequestHandler
from core.database import init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """获取监控账号列表"""
        try:
            conn = init_db()
            cursor = conn.execute("""
                SELECT id, nickname, avatar_url, follower_count, video_count, is_monitored, updated_at
                FROM authors
                ORDER BY is_monitored DESC, follower_count DESC
            """)

            authors = []
            for row in cursor.fetchall():
                authors.append({
                    "id": row[0],
                    "nickname": row[1],
                    "avatar_url": row[2],
                    "follower_count": row[3],
                    "video_count": row[4],
                    "is_monitored": bool(row[5]),
                    "updated_at": row[6],
                })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "data": authors}, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_POST(self):
        """添加/更新监控账号"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            action = body.get("action", "toggle")
            author_id = body.get("author_id", "")

            conn = init_db()

            if action == "toggle":
                conn.execute("""
                    UPDATE authors SET is_monitored = CASE WHEN is_monitored = 1 THEN 0 ELSE 1 END
                    WHERE id = ?
                """, (author_id,))
                conn.commit()

            response = {"ok": True, "message": "操作成功"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
