"""抖音热点雷达 - 数据库模块"""

import os
import sqlite3
from core.config import Config


def get_connection():
    """获取数据库连接

    优先使用 Turso（线上），降级到本地 SQLite（开发）。
    Turso 通过 libsql_experimental 连接，本地用标准 sqlite3。
    """
    if Config.TURSO_DATABASE_URL:
        try:
            import libsql
            conn = libsql.connect(
                database=Config.TURSO_DATABASE_URL,
                auth_token=Config.TURSO_AUTH_TOKEN,
            )
            return conn
        except ImportError:
            print("[WARN] libsql 未安装，降级到本地 SQLite")

    # 本地 SQLite
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "local.db")
    conn = sqlite3.connect(db_path)
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()

    # 关闭外键检查（兼容旧表结构）
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
    except Exception:
        pass

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 强制重建 alerts 表去掉外键（Turso 上旧表有 FOREIGN KEY 导致插入失败）
    try:
        # 检测是否有外键约束
        cursor = conn.execute("PRAGMA foreign_key_list('alerts')")
        fkeys = cursor.fetchall()
        if fkeys:
            conn.execute("ALTER TABLE alerts RENAME TO _alerts_old")
            conn.execute("""
                CREATE TABLE alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    alert_type TEXT,
                    score REAL,
                    message TEXT,
                    sent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO alerts SELECT * FROM _alerts_old
            """)
            conn.execute("DROP TABLE _alerts_old")
            print("[MIGRATE] alerts 表已重建（去掉外键）")
    except Exception:
        pass  # PRAGMA 可能在 Turso 上不支持，跳过

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


# ========== 聊天交互用查询 ==========


def get_top_videos(conn, limit: int = 5):
    """获取同行近期 TOP 视频（按点赞排序）"""
    cursor = conn.execute("""
        SELECT v.id, v.title, a.nickname as author_name,
               vs.like_count, vs.comment_count, vs.collect_count
        FROM videos v
        JOIN authors a ON v.author_id = a.id
        JOIN video_snapshots vs ON v.id = vs.video_id
        WHERE a.is_monitored = 1
        AND v.created_at > strftime('%s', 'now', '-15 days')
        AND vs.id IN (SELECT MAX(id) FROM video_snapshots GROUP BY video_id)
        ORDER BY vs.like_count DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    return [{
        "id": r[0], "title": r[1], "author_name": r[2],
        "like_count": r[3], "comment_count": r[4], "collect_count": r[5],
    } for r in rows] if rows else []


def get_recent_hot_topics(conn, limit: int = 10):
    """获取最近一批热搜"""
    cursor = conn.execute("""
        SELECT title, hot_value FROM trending_topics
        ORDER BY snapshot_at DESC, hot_value DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    return [{"title": r[0], "hot_value": r[1]} for r in rows] if rows else []


def get_system_status(conn):
    """获取系统运行状态摘要"""
    status = {}

    cursor = conn.execute("SELECT COUNT(*) FROM authors WHERE is_monitored = 1")
    status["monitored_authors"] = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM videos")
    status["total_videos"] = cursor.fetchone()[0]

    cursor = conn.execute("SELECT MAX(snapshot_at) FROM video_snapshots")
    row = cursor.fetchone()
    status["last_snapshot"] = row[0] if row and row[0] else "暂无"

    cursor = conn.execute("""
        SELECT COUNT(*) FROM alerts
        WHERE created_at > datetime('now', '-24 hours')
        AND alert_type IN ('explosive', 'trending', 'potential')
    """)
    status["recent_alerts"] = cursor.fetchone()[0]

    return status
