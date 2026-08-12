"""SQLite database management for PostureGuard.

All queries use context-manager connections so every call is safe to
call from any thread (each creates its own connection).
"""

from __future__ import annotations

import sqlite3
import logging
from collections import Counter
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from posture_guard.utils import constants
from posture_guard.data.models import PostureEventRecord, AlertRecord, PostureStats

logger = logging.getLogger(__name__)


class PostureDatabase:
    """Manages SQLite persistence for PostureGuard."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or constants.DB_PATH
        self._init_db()

    # ──────────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────────

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ──────────────────────────────────────────────
    # Schema
    # ──────────────────────────────────────────────

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        start_time  TEXT NOT NULL,
                        end_time    TEXT DEFAULT ''
                    );

                    CREATE TABLE IF NOT EXISTS posture_events (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id   INTEGER NOT NULL,
                        timestamp    TEXT NOT NULL,
                        state        TEXT NOT NULL,
                        issues       TEXT DEFAULT '',
                        metrics_json TEXT DEFAULT '{}',
                        duration_sec REAL DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    );

                    CREATE TABLE IF NOT EXISTS alerts (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id  INTEGER NOT NULL,
                        timestamp   TEXT NOT NULL,
                        level       INTEGER NOT NULL,
                        alert_type  TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    );
                """)
        except sqlite3.Error as e:
            logger.error("Failed to initialize database: %s", e)

    # ──────────────────────────────────────────────
    # Sessions
    # ──────────────────────────────────────────────

    def create_session(self) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO sessions (start_time) VALUES (?)",
                    (datetime.now().isoformat(),)
                )
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error("Error creating session: %s", e)
            return -1

    def end_session(self, session_id: int) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET end_time = ? WHERE id = ?",
                    (datetime.now().isoformat(), session_id)
                )
        except sqlite3.Error as e:
            logger.error("Error ending session: %s", e)

    # ──────────────────────────────────────────────
    # Events & Alerts
    # ──────────────────────────────────────────────

    def insert_posture_event(self, event: PostureEventRecord) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO posture_events
                        (session_id, timestamp, state, issues, metrics_json, duration_sec)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event.session_id, event.timestamp, event.state,
                     event.issues, event.metrics_json, event.duration_sec)
                )
        except sqlite3.Error as e:
            logger.error("Error inserting posture event: %s", e)

    def insert_alert(self, alert: AlertRecord) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO alerts (session_id, timestamp, level, alert_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (alert.session_id, alert.timestamp, alert.level, alert.alert_type)
                )
        except sqlite3.Error as e:
            logger.error("Error inserting alert: %s", e)

    # ──────────────────────────────────────────────
    # Aggregated Stats
    # ──────────────────────────────────────────────

    def _query_events(self, conn: sqlite3.Connection, date_str: str) -> list:
        """Return all events for a given date (YYYY-MM-DD)."""
        prefix = date_str + "T"
        rows = conn.execute(
            """
            SELECT state, issues, duration_sec, timestamp
            FROM posture_events
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp
            """,
            (prefix, (date.fromisoformat(date_str) + timedelta(days=1)).isoformat() + "T")
        ).fetchall()
        return rows

    def get_daily_stats(self, date_str: str) -> list[PostureStats]:
        """Return hourly stats for a given date."""
        buckets: list[PostureStats] = [
            PostureStats(period_label=f"{h:02d}:00") for h in range(24)
        ]
        try:
            with self._get_connection() as conn:
                rows = self._query_events(conn, date_str)
                for row in rows:
                    try:
                        hour = datetime.fromisoformat(row["timestamp"]).hour
                    except ValueError:
                        continue
                    s = buckets[hour]
                    dur = row["duration_sec"]
                    s.total_seconds += dur
                    if row["state"] == "good":
                        s.good_seconds += dur
                    else:
                        s.bad_seconds += dur
        except sqlite3.Error as e:
            logger.error("Error getting daily stats: %s", e)
        return buckets

    def get_weekly_stats(self, date_str: str) -> list[PostureStats]:
        """Return per-day stats for the week containing date_str."""
        day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            target = date.today()

        # Monday of the week
        monday = target - timedelta(days=target.weekday())
        buckets: list[PostureStats] = [
            PostureStats(period_label=day_names[i]) for i in range(7)
        ]
        try:
            with self._get_connection() as conn:
                for i in range(7):
                    day = monday + timedelta(days=i)
                    rows = self._query_events(conn, day.isoformat())
                    s = buckets[i]
                    for row in rows:
                        dur = row["duration_sec"]
                        s.total_seconds += dur
                        if row["state"] == "good":
                            s.good_seconds += dur
                        else:
                            s.bad_seconds += dur
        except sqlite3.Error as e:
            logger.error("Error getting weekly stats: %s", e)
        return buckets

    def get_monthly_stats(self, year: int, month: int) -> list[PostureStats]:
        """Return per-week stats for a given month."""
        buckets: list[PostureStats] = [
            PostureStats(period_label=f"Sem {i+1}") for i in range(5)
        ]
        try:
            with self._get_connection() as conn:
                first = date(year, month, 1)
                last = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
                d = first
                while d < last:
                    rows = self._query_events(conn, d.isoformat())
                    # Which week within the month (0-based)
                    week_idx = min((d.day - 1) // 7, 4)
                    s = buckets[week_idx]
                    for row in rows:
                        dur = row["duration_sec"]
                        s.total_seconds += dur
                        if row["state"] == "good":
                            s.good_seconds += dur
                        else:
                            s.bad_seconds += dur
                    d += timedelta(days=1)
        except sqlite3.Error as e:
            logger.error("Error getting monthly stats: %s", e)
        return buckets

    def get_summary(self, date_str: str) -> dict:
        """Return summary dict for the stats window.

        Keys: pct (int), time (str), alerts (int), streak (int)
        """
        result = {"pct": 0, "time": "0m", "alerts": 0, "streak": 0}
        try:
            with self._get_connection() as conn:
                # Today's good/bad totals
                rows = self._query_events(conn, date_str)
                good_sec = sum(r["duration_sec"] for r in rows if r["state"] == "good")
                total_sec = sum(r["duration_sec"] for r in rows)
                result["pct"] = int((good_sec / total_sec * 100) if total_sec > 0 else 0)

                mins = int(total_sec // 60)
                if mins >= 60:
                    result["time"] = f"{mins // 60}h {mins % 60}m"
                else:
                    result["time"] = f"{mins}m"

                # Today's alerts
                prefix = date_str + "T"
                next_day = (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()
                alert_count = conn.execute(
                    "SELECT COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ?",
                    (prefix, next_day + "T")
                ).fetchone()[0]
                result["alerts"] = alert_count

                # Streak: consecutive days with at least some data
                streak = 0
                check = date.fromisoformat(date_str)
                while True:
                    rows_check = self._query_events(conn, check.isoformat())
                    if not rows_check:
                        break
                    streak += 1
                    check -= timedelta(days=1)
                result["streak"] = streak

        except (sqlite3.Error, ValueError) as e:
            logger.error("Error getting summary: %s", e)
        return result

    def close(self) -> None:
        pass  # connections are managed per-call
