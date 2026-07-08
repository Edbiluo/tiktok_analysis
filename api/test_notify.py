"""API - 测试推送"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.notifier import Notifier


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            notifier = Notifier()
            success = notifier.send_markdown("""🧪 **测试消息**

抖音热点雷达已成功连接！

> 如果你看到这条消息，说明推送通道正常。""")

            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            msg = {"ok": success, "message": "已发送" if success else "发送失败"}
            self.wfile.write(json.dumps(msg, ensure_ascii=False).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
