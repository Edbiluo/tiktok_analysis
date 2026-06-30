"""API - 测试企业微信推送"""

import json
from http.server import BaseHTTPRequestHandler
from core.notifier import WeComNotifier


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """发送一条测试消息"""
        try:
            notifier = WeComNotifier()
            success = notifier.send_markdown("""🧪 **测试消息**

抖音热点雷达已成功连接企业微信！

> 如果你看到这条消息，说明推送通道正常。

接下来系统会自动监控同行动态，发现起势视频时会推送预警。""")

            if success:
                response = {"ok": True, "message": "测试消息已发送"}
            else:
                response = {"ok": False, "error": "发送失败，请检查企微配置"}

            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

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
