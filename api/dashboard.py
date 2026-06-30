"""API - 仪表盘数据"""

import json
from http.server import BaseHTTPRequestHandler
from core.database import init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """获取仪表盘概览数据"""
        try:
            conn = init_db()

            # 获取起势视频（最近 24 小时内评分最高的）
            cursor = conn.execute("""
                SELECT
                    v.id, v.title, v.author_id, v.cover_url, v.created_at,
                    a.nickname as author_name, a.avatar_url,
                    vs.play_count, vs.like_count, vs.comment_count,
                    vs.share_count, vs.collect_count, vs.snapshot_at,
                    al.score, al.alert_type
                FROM videos v
                LEFT JOIN authors a ON v.author_id = a.id
                LEFT JOIN video_snapshots vs ON v.id = vs.video_id
                LEFT JOIN alerts al ON v.id = al.video_id
                WHERE vs.id IN (
                    SELECT MAX(id) FROM video_snapshots GROUP BY video_id
                )
                ORDER BY al.score DESC NULLS LAST, vs.like_count DESC
                LIMIT 20
            """)

            videos = []
            for row in cursor.fetchall():
                videos.append({
                    "id": row[0],
                    "title": row[1],
                    "author_id": row[2],
                    "cover_url": row[3],
                    "created_at": row[4],
                    "author_name": row[5],
                    "avatar_url": row[6],
                    "play_count": row[7],
                    "like_count": row[8],
                    "comment_count": row[9],
                    "share_count": row[10],
                    "collect_count": row[11],
                    "snapshot_at": row[12],
                    "score": row[13],
                    "alert_type": row[14],
                })

            # 获取最新热搜
            cursor = conn.execute("""
                SELECT title, hot_value, snapshot_at
                FROM trending_topics
                ORDER BY snapshot_at DESC, hot_value DESC
                LIMIT 20
            """)

            hot_topics = []
            for row in cursor.fetchall():
                hot_topics.append({
                    "title": row[0],
                    "hot_value": row[1],
                    "snapshot_at": row[2],
                })

            # 统计概览
            cursor = conn.execute("SELECT COUNT(*) FROM authors WHERE is_monitored = 1")
            author_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM videos")
            video_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM alerts WHERE score >= 60")
            alert_count = cursor.fetchone()[0]

            response = {
                "ok": True,
                "data": {
                    "overview": {
                        "monitored_authors": author_count,
                        "total_videos": video_count,
                        "trending_alerts": alert_count,
                    },
                    "trending_videos": videos,
                    "hot_topics": hot_topics,
                }
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
