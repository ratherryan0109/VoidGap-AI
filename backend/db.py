import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "skillgap.db")


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS profiles (
                student_id INTEGER PRIMARY KEY,
                current_skills TEXT NOT NULL,   -- JSON: [{skill, level}]
                projects TEXT NOT NULL,         -- JSON: [{title, description, skills:[]}]
                github_username TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS target_roles (
                student_id INTEGER PRIMARY KEY,
                role_title TEXT NOT NULL,
                job_description TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS roadmap_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                skill TEXT NOT NULL,
                priority_rank INTEGER NOT NULL,
                reason TEXT,
                suggested_project TEXT,
                status TEXT DEFAULT 'pending',  -- pending | in_progress | done
                FOREIGN KEY(student_id) REFERENCES students(id)
            );
            """
        )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_profile(student_id, current_skills, projects, github_username=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO profiles (student_id, current_skills, projects, github_username)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(student_id) DO UPDATE SET
                 current_skills=excluded.current_skills,
                 projects=excluded.projects,
                 github_username=excluded.github_username""",
            (student_id, json.dumps(current_skills), json.dumps(projects), github_username),
        )


def get_profile(student_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE student_id=?", (student_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "current_skills": json.loads(row["current_skills"]),
            "projects": json.loads(row["projects"]),
            "github_username": row["github_username"],
        }


def save_target_role(student_id, role_title, job_description):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO target_roles (student_id, role_title, job_description)
               VALUES (?, ?, ?)
               ON CONFLICT(student_id) DO UPDATE SET
                 role_title=excluded.role_title,
                 job_description=excluded.job_description""",
            (student_id, role_title, job_description),
        )


def get_target_role(student_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM target_roles WHERE student_id=?", (student_id,)
        ).fetchone()
        return dict(row) if row else None


def replace_roadmap(student_id, items):
    """items: list of dicts {skill, priority_rank, reason, suggested_project}"""
    with get_conn() as conn:
        # preserve status of items that still exist (adaptive, not destructive)
        existing = {
            r["skill"]: r["status"]
            for r in conn.execute(
                "SELECT skill, status FROM roadmap_items WHERE student_id=?",
                (student_id,),
            ).fetchall()
        }
        conn.execute("DELETE FROM roadmap_items WHERE student_id=?", (student_id,))
        for item in items:
            status = existing.get(item["skill"], "pending")
            conn.execute(
                """INSERT INTO roadmap_items
                   (student_id, skill, priority_rank, reason, suggested_project, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    student_id,
                    item["skill"],
                    item["priority_rank"],
                    item.get("reason", ""),
                    item.get("suggested_project", ""),
                    status,
                ),
            )


def get_roadmap(student_id):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, skill, priority_rank, reason, suggested_project, status
               FROM roadmap_items WHERE student_id=? ORDER BY priority_rank ASC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_progress(item_id, status):
    with get_conn() as conn:
        conn.execute(
            "UPDATE roadmap_items SET status=? WHERE id=?", (status, item_id)
        )


def create_or_get_student(name):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM students WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO students (name) VALUES (?)", (name,))
        return cur.lastrowid
