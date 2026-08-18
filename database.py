"""SQLite database utilities for LLM Persona Studio.

The database stores projects, personas, chat logs and project attachment metadata.
It is intentionally lightweight for an MSc prototype and can be replaced with a
managed database later if the project grows.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).with_name("llm_persona_studio.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                platform TEXT,
                domain TEXT,
                target_task TEXT,
                browser_id TEXT
            )
            """
        )
        project_columns = {row["name"] for row in cur.execute("PRAGMA table_info(projects)").fetchall()}
        if "browser_id" not in project_columns:
            cur.execute("ALTER TABLE projects ADD COLUMN browser_id TEXT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_browser_id ON projects(browser_id)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                user_group TEXT NOT NULL,
                age_group TEXT,
                digital_literacy TEXT,
                accessibility_need TEXT,
                device TEXT,
                language_preference TEXT,
                goal TEXT,
                frustration TEXT,
                context TEXT,
                system_prompt TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                persona_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                user_question TEXT NOT NULL,
                persona_response TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(persona_id) REFERENCES personas(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT,
                mime_type TEXT,
                path TEXT NOT NULL,
                extracted_text TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        conn.commit()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def insert_project(
    title: str,
    description: str,
    platform: str,
    domain: str,
    target_task: str,
    browser_id: str,
) -> int:
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO projects (created_at, title, description, platform, domain, target_task, browser_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now_iso(), title, description, platform, domain, target_task, browser_id),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_project(project_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if not project_id:
        return None
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def get_all_projects(browser_id: str) -> List[Dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE browser_id = ? ORDER BY id DESC",
            (browser_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def insert_persona(project_id: int, persona: Dict[str, Any]) -> int:
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO personas (
                project_id, created_at, name, user_group, age_group, digital_literacy,
                accessibility_need, device, language_preference, goal, frustration,
                context, system_prompt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                now_iso(),
                persona.get("name", ""),
                persona.get("user_group", ""),
                persona.get("age_group", ""),
                persona.get("digital_literacy", ""),
                persona.get("accessibility_need", ""),
                persona.get("device", ""),
                persona.get("language_preference", ""),
                persona.get("goal", ""),
                persona.get("frustration", ""),
                persona.get("context", ""),
                persona.get("system_prompt", ""),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_persona(persona_id: int, persona: Dict[str, Any]) -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE personas
            SET name = ?, user_group = ?, age_group = ?, digital_literacy = ?,
                accessibility_need = ?, device = ?, language_preference = ?, goal = ?,
                frustration = ?, context = ?, system_prompt = ?
            WHERE id = ?
            """,
            (
                persona.get("name", ""),
                persona.get("user_group", ""),
                persona.get("age_group", ""),
                persona.get("digital_literacy", ""),
                persona.get("accessibility_need", ""),
                persona.get("device", ""),
                persona.get("language_preference", ""),
                persona.get("goal", ""),
                persona.get("frustration", ""),
                persona.get("context", ""),
                persona.get("system_prompt", ""),
                persona_id,
            ),
        )
        conn.commit()


def get_persona(persona_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if not persona_id:
        return None
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        return dict(row) if row else None


def get_personas_for_project(project_id: Optional[int]) -> List[Dict[str, Any]]:
    if not project_id:
        return []
    with closing(get_connection()) as conn:
        rows = conn.execute("SELECT * FROM personas WHERE project_id = ? ORDER BY id ASC", (project_id,)).fetchall()
        return [dict(row) for row in rows]


def insert_chat(project_id: int, persona_id: int, user_question: str, persona_response: str) -> int:
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_logs (project_id, persona_id, created_at, user_question, persona_response)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, persona_id, now_iso(), user_question, persona_response),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_chat_logs_for_project(project_id: Optional[int]) -> List[Dict[str, Any]]:
    if not project_id:
        return []
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT * FROM chat_logs WHERE project_id = ? ORDER BY id ASC",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def insert_attachment(
    project_id: int,
    filename: str,
    file_type: str,
    mime_type: str,
    path: str,
    extracted_text: str = "",
) -> int:
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO project_attachments (
                project_id, created_at, filename, file_type, mime_type, path, extracted_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, now_iso(), filename, file_type, mime_type, path, extracted_text),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_attachments_for_project(project_id: Optional[int]) -> List[Dict[str, Any]]:
    if not project_id:
        return []
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT * FROM project_attachments WHERE project_id = ? ORDER BY id ASC",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]
