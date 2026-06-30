"""抖音热点雷达 - 数据库模块"""

import libsql_experimental as libsql
from core.config import Config


def get_connection():
    """获取数据库连接"""
    if Config.TURSO_DATABASE_URL:
        conn = libsql.connect(
            database=Config.TURSO_DATABASE_URL,
            auth_token=Config.TURSO_AUTH_TOKEN,
        )
    else:
        # 本地开发用 SQLite
        conn = libsql.connect(database="local.db")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id TEXT PRIMARY KEY,
            nickname TEXT,
            avatar_url TEXT,
            follower_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            total_favorited INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            is_monitored INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            author_id TEXT,
            title TEXT,
            cover_url TEXT,
            video_url TEXT,
            duration INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES authors(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS video_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            play_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            collect_count INTEGER DEFAULT 0,
            snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trending_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            hot_value INTEGER DEFAULT 0,
            category TEXT,
            snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            alert_type TEXT,
            score REAL,
            message TEXT,
            sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    """)

    conn.commit()
    return conn


def save_author(conn, author: dict):
    """保存/更新作者信息"""
    conn.execute("""
        INSERT INTO authors (id, nickname, avatar_url, follower_count, video_count, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            nickname = excluded.nickname,
            avatar_url = excluded.avatar_url,
            follower_count = excluded.follower_count,
            video_count = excluded.video_count,
            updated_at = CURRENT_TIMESTAMP
    """, (
        author["id"],
        author.get("nickname", ""),
        author.get("avatar_url", ""),
        author.get("follower_count", 0),
        author.get("video_count", 0),
    ))
    conn.commit()


def save_video(conn, video: dict):
    """保存视频基本信息"""
    conn.execute("""
        INSERT INTO videos (id, author_id, title, cover_url, duration, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            cover_url = excluded.cover_url
    """, (
        video["id"],
        video.get("author_id", ""),
        video.get("title", ""),
        video.get("cover_url", ""),
        video.get("duration", 0),
        video.get("created_at", ""),
    ))
    conn.commit()


def save_snapshot(conn, snapshot: dict):
    """保存视频数据快照"""
    conn.execute("""
        INSERT INTO video_snapshots (video_id, play_count, like_count, comment_count, share_count, collect_count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        snapshot["video_id"],
        snapshot.get("play_count", 0),
        snapshot.get("like_count", 0),
        snapshot.get("comment_count", 0),
        snapshot.get("share_count", 0),
        snapshot.get("collect_count", 0),
    ))
    conn.commit()


def get_video_history(conn, video_id: str, limit: int = 10):
    """获取视频历史快照"""
    cursor = conn.execute("""
        SELECT play_count, like_count, comment_count, share_count, collect_count, snapshot_at
        FROM video_snapshots
        WHERE video_id = ?
        ORDER BY snapshot_at DESC
        LIMIT ?
    """, (video_id, limit))
    return cursor.fetchall()


def get_author_avg_stats(conn, author_id: str, recent_count: int = 20):
    """获取作者近期视频平均数据"""
    cursor = conn.execute("""
        SELECT
            AVG(vs.like_count) as avg_likes,
            AVG(vs.comment_count) as avg_comments,
            AVG(vs.share_count) as avg_shares,
            AVG(vs.collect_count) as avg_collects,
            AVG(vs.play_count) as avg_plays
        FROM videos v
        JOIN video_snapshots vs ON v.id = vs.video_id
        WHERE v.author_id = ?
        AND vs.id IN (
            SELECT MAX(id) FROM video_snapshots
            WHERE video_id IN (
                SELECT id FROM videos WHERE author_id = ?
                ORDER BY created_at DESC LIMIT ?
            )
            GROUP BY video_id
        )
    """, (author_id, author_id, recent_count))
    row = cursor.fetchone()
    if row:
        return {
            "avg_likes": row[0] or 0,
            "avg_comments": row[1] or 0,
            "avg_shares": row[2] or 0,
            "avg_collects": row[3] or 0,
            "avg_plays": row[4] or 0,
        }
    return None
