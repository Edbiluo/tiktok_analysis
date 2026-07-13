"""API - 企业微信回调（URL 验证 + 消息接收）

GET: 企微配置"接收消息服务器"时的 URL 验证（签名校验 + AES 解密 echostr）
POST: 接收群聊 @机器人 的消息，交给 ChatHandler 处理
"""

import os
import sys
import json
import hashlib
import base64
import struct
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree

# 让 api/ 下的文件能 import core/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从环境变量读取
TOKEN = os.environ.get("WECOM_CALLBACK_TOKEN", "")
ENCODING_AES_KEY = os.environ.get("WECOM_CALLBACK_AES_KEY", "")
CORP_ID = os.environ.get("WECOM_CORP_ID", "")


def verify_signature(token, timestamp, nonce, encrypt_str, msg_signature):
    """验证签名"""
    sort_list = sorted([token, timestamp, nonce, encrypt_str])
    sha = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
    return sha == msg_signature


def decrypt_message(encoding_aes_key, encrypted_str):
    """AES-CBC 解密企微消息"""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        from Cryptodome.Cipher import AES

    # EncodingAESKey 是 Base64 编码的 256 位密钥（43字符 + 补 "="）
    aes_key = base64.b64decode(encoding_aes_key + "=")

    # AES-CBC 解密，IV 是 key 的前 16 字节
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    decrypted = cipher.decrypt(base64.b64decode(encrypted_str))

    # 去除 PKCS#7 填充
    pad_len = decrypted[-1]
    if isinstance(pad_len, int):
        content = decrypted[:-pad_len]
    else:
        content = decrypted[:-ord(pad_len)]

    # 解析：16字节随机串 + 4字节消息长度 + 消息内容 + CorpID
    msg_len = struct.unpack(">I", content[16:20])[0]
    msg = content[20:20 + msg_len].decode("utf-8")

    return msg


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """响应企微的 URL 验证请求"""
        query = parse_qs(urlparse(self.path).query)

        msg_signature = query.get("msg_signature", [""])[0]
        timestamp = query.get("timestamp", [""])[0]
        nonce = query.get("nonce", [""])[0]
        echostr = query.get("echostr", [""])[0]

        if not all([msg_signature, timestamp, nonce, echostr]):
            # 普通访问，非验证请求
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "msg": "wecom callback ready"}).encode())
            return

        # 1. 验证签名
        if not verify_signature(TOKEN, timestamp, nonce, echostr, msg_signature):
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"signature verification failed")
            return

        # 2. 解密 echostr
        try:
            reply_echostr = decrypt_message(ENCODING_AES_KEY, echostr)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"decrypt failed: {e}".encode())
            return

        # 3. 返回解密后的明文
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(reply_echostr.encode())

    def do_POST(self):
        """接收企微推送的消息，交给 ChatHandler 处理"""
        try:
            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else ""

            # 从 query string 取验签参数
            query = parse_qs(urlparse(self.path).query)
            msg_signature = query.get("msg_signature", [""])[0]
            timestamp = query.get("timestamp", [""])[0]
            nonce = query.get("nonce", [""])[0]

            # 解析外层 XML 提取 <Encrypt>
            xml_root = ElementTree.fromstring(body)
            encrypt_str = xml_root.findtext("Encrypt") or ""

            if not encrypt_str:
                print("[CALLBACK] POST body 无 <Encrypt> 字段")
                self._reply_success()
                return

            # 验签
            if msg_signature and not verify_signature(TOKEN, timestamp, nonce, encrypt_str, msg_signature):
                print("[CALLBACK] POST 签名验证失败")
                self._reply_success()
                return

            # AES 解密
            try:
                decrypted_xml = decrypt_message(ENCODING_AES_KEY, encrypt_str)
            except Exception as e:
                print(f"[CALLBACK] POST 解密失败: {e}")
                self._reply_success()
                return

            # 交给 ChatHandler 处理
            from core.chat_handler import ChatHandler
            chat = ChatHandler()
            try:
                chat.handle(decrypted_xml)
            finally:
                chat.close()

        except Exception as e:
            print(f"[CALLBACK] do_POST 异常: {e}")

        self._reply_success()

    def _reply_success(self):
        """返回 200 success（企微要求）"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"success")
