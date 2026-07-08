"""API - 手动触发采集"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.collect import run_collection


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """手动触发一次数据采集"""
        try:
            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = {}
            if content_length > 0:
                body = json.loads(self.rfile.read(content_length))

            hot_only = body.get("hot_only", False)
            notify = body.get("notify", True)

            # 执行采集
            run_collection(hot_only=hot_only, notify=notify)

            response = {
                "ok": True,
                "message": "采集完成",
            }

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
        """CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
