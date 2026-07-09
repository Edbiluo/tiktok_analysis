"""API - 触发采集（轻量中转，秒回 + 异步调 GitHub Actions）"""

import json
import ssl
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import Config


def dispatch_github_actions(mode: str = "full") -> bool:
    """调用 GitHub Actions workflow_dispatch，让 Actions 跑实际采集"""
    import httpx

    token = os.environ.get("GITHUB_PAT", "")
    if not token:
        print("[WARN] GITHUB_PAT 未配置，无法触发 Actions")
        return False

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        resp = httpx.post(
            "https://api.github.com/repos/Edbiluo/tiktok_analysis/actions/workflows/collect.yml/dispatches",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "ref": "main",
                "inputs": {"mode": mode, "notify": "true"},
            },
            verify=ctx,
            timeout=10,
        )
        # 204 No Content = 成功触发
        return resp.status_code == 204
    except Exception as e:
        print(f"[ERROR] 触发 Actions 失败: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """cron-job.org 定时触发"""
        self._dispatch()

    def do_POST(self):
        """前端手动触发"""
        self._dispatch()

    def _dispatch(self):
        try:
            # 读 POST body（如果有）
            body = {}
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = json.loads(self.rfile.read(content_length))

            mode = "hot-only" if body.get("hot_only") else "full"

            # 秒回：触发 GitHub Actions，不等结果
            ok = dispatch_github_actions(mode)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if ok:
                msg = {"ok": True, "message": "已触发采集（后台运行中）"}
            else:
                msg = {"ok": False, "message": "触发失败，请检查 GITHUB_PAT 配置"}

            self.wfile.write(json.dumps(msg, ensure_ascii=False).encode())

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
