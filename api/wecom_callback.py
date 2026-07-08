"""API - 企业微信回调验证

企微配置"接收消息服务器"时会发 GET 请求验证，
只需要把 echostr 原样返回即可通过验证。
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """响应企微的 URL 验证请求"""
        query = parse_qs(urlparse(self.path).query)

        # 企微验证时会带 echostr 参数，原样返回即通过
        echostr = query.get("echostr", [""])[0]

        if echostr:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(echostr.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "msg": "wecom callback ready"}).encode())

    def do_POST(self):
        """接收企微推送的消息（暂不处理）"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"success")
