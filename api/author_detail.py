"""API - 作者详情（基本信息 + 最近数据最好的作品）"""

import json
import sys
import os
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """获取作者详情和 TOP 作品"""
        try:
            query = parse_qs(urlparse(self.path).query)
            author_id = query.get("id", [""])[0]
            period = query.get("period", ["all"])[0]  # month, half_year, year, all

            if not author_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "缺少 id 参数"}).encode())
                return

            conn = init_db()

            # 计算时间筛选条件
            now = int(time.time())
            if period == "month":
                since_ts = now - 30 * 86400
            elif period == "half_year":
                since_ts = now - 180 * 86400
            elif period == "year":
                since_ts = now - 365 * 86400
            else:
                since_ts = 0

            # 获取作者基本信息
            cursor = conn.execute("""
                SELECT id, nickname, avatar_url, follower_count, video_count, updated_at
                FROM authors WHERE id = ?
            """, (author_id,))
            row = cursor.fetchone()

            if not row:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "作者不存在"}).encode())
                return

            author = {
                "id": row[0],
                "nickname": row[1],
                "avatar_url": row[2],
                "follower_count": row[3],
                "video_count": row[4],
                "updated_at": row[5],
            }

            # 获取该作者作品，按热度排序，带时间筛选
            time_filter = "AND v.created_at >= ?" if since_ts > 0 else ""
            params = [author_id, author_id]
            if since_ts > 0:
                params = [author_id, since_ts, author_id]

            cursor = conn.execute(f"""
                SELECT
                    v.id, v.title, v.created_at,
                    vs.play_count, vs.like_count, vs.comment_count,
                    vs.share_count, vs.collect_count,
                    (vs.like_count + vs.comment_count + vs.share_count) as hot_score
                FROM videos v
                LEFT JOIN video_snapshots vs ON v.id = vs.video_id
                WHERE v.author_id = ? {time_filter}
                AND vs.id IN (
                    SELECT MAX(id) FROM video_snapshots
                    WHERE video_id IN (SELECT id FROM videos WHERE author_id = ?)
                    GROUP BY video_id
                )
                ORDER BY hot_score DESC
                LIMIT 30
            """, params)

            videos = []
            for row in cursor.fetchall():
                videos.append({
                    "id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "play_count": row[3],
                    "like_count": row[4],
                    "comment_count": row[5],
                    "share_count": row[6],
                    "collect_count": row[7],
                    "hot_score": row[8],
                })

            # 统计平均数据（同样带时间筛选）
            cursor = conn.execute(f"""
                SELECT
                    AVG(vs.like_count),
                    AVG(vs.comment_count),
                    AVG(vs.share_count),
                    AVG(vs.collect_count),
                    AVG(vs.play_count),
                    COUNT(DISTINCT v.id)
                FROM videos v
                LEFT JOIN video_snapshots vs ON v.id = vs.video_id
                WHERE v.author_id = ? {time_filter}
                AND vs.id IN (
                    SELECT MAX(id) FROM video_snapshots
                    WHERE video_id IN (SELECT id FROM videos WHERE author_id = ?)
                    GROUP BY video_id
                )
            """, params)
            stats_row = cursor.fetchone()
            avg_stats = {
                "avg_likes": round(stats_row[0] or 0),
                "avg_comments": round(stats_row[1] or 0),
                "avg_shares": round(stats_row[2] or 0),
                "avg_collects": round(stats_row[3] or 0),
                "avg_plays": round(stats_row[4] or 0),
                "total_tracked": stats_row[5] or 0,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "data": {
                    "author": author,
                    "avg_stats": avg_stats,
                    "top_videos": videos,
                }
            }, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
