"""
db.py — Database layer.
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

DB_PATH = Path("family_quest.db")


# ── Connection ─────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS heroes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            class            TEXT    NOT NULL,
            color            TEXT    NOT NULL DEFAULT '#3498db',
            max_hp           INTEGER NOT NULL DEFAULT 100,
            current_hp       INTEGER NOT NULL DEFAULT 100,
            xp               INTEGER NOT NULL DEFAULT 0,
            level            INTEGER NOT NULL DEFAULT 1,
            coins            INTEGER NOT NULL DEFAULT 0,
            is_knocked_out   INTEGER NOT NULL DEFAULT 0,
            knockout_until   TEXT,
            sort_order       INTEGER NOT NULL DEFAULT 0,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS task_templates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            hero_id      INTEGER NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
            title        TEXT    NOT NULL,
            description  TEXT,
            difficulty   TEXT    NOT NULL DEFAULT 'medium',
            xp_reward    INTEGER NOT NULL,
            coin_reward  INTEGER NOT NULL,
            boss_damage  INTEGER NOT NULL,
            miss_damage  INTEGER NOT NULL,
            is_active    INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hero_id       INTEGER NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
            template_id   INTEGER REFERENCES task_templates(id),
            title         TEXT    NOT NULL,
            description   TEXT,
            difficulty    TEXT    NOT NULL DEFAULT 'medium',
            xp_reward     INTEGER NOT NULL,
            coin_reward   INTEGER NOT NULL,
            boss_damage   INTEGER NOT NULL,
            miss_damage   INTEGER NOT NULL,
            state         TEXT    NOT NULL DEFAULT 'pending',
            task_date     TEXT    NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            completed_at  TEXT,
            approved_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS bosses (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            name               TEXT    NOT NULL,
            image_key          TEXT    NOT NULL,
            lore               TEXT,
            color              TEXT    NOT NULL DEFAULT '#8B0000',
            max_hp             INTEGER NOT NULL,
            current_hp         INTEGER NOT NULL,
            week_number        INTEGER NOT NULL DEFAULT 1,
            week_start         TEXT    NOT NULL,
            week_end           TEXT    NOT NULL,
            is_defeated        INTEGER NOT NULL DEFAULT 0,
            defeated_at        TEXT,
            created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT    NOT NULL,
            hero_id     INTEGER REFERENCES heroes(id),
            message     TEXT    NOT NULL,
            metadata    TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rewards (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            description      TEXT,
            cost_coins       INTEGER NOT NULL DEFAULT 0,
            is_family_reward INTEGER NOT NULL DEFAULT 0,
            is_active        INTEGER NOT NULL DEFAULT 1,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reward_claims (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            reward_id    INTEGER NOT NULL REFERENCES rewards(id),
            hero_id      INTEGER REFERENCES heroes(id),
            cost_coins   INTEGER NOT NULL DEFAULT 0,
            is_fulfilled INTEGER NOT NULL DEFAULT 0,
            claimed_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            fulfilled_at TEXT
        );
        """)
        # Migrate bosses table if week_number column missing (for existing DBs)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bosses)").fetchall()]
        if "week_number" not in cols:
            conn.execute("ALTER TABLE bosses ADD COLUMN week_number INTEGER NOT NULL DEFAULT 1")


# ── Heroes ─────────────────────────────────────────────────────────────────────

def get_all_heroes(conn) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT *, class AS hero_class FROM heroes ORDER BY sort_order, id"
    ).fetchall()


def get_hero(conn, hero_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT *, class AS hero_class FROM heroes WHERE id = ?", (hero_id,)
    ).fetchone()


def create_hero(conn, name: str, hero_class: str, color: str) -> int:
    from config import HERO_BASE_HP, HERO_HP_PER_LEVEL
    max_hp = HERO_BASE_HP.get(hero_class, 100)
    sort_order = conn.execute("SELECT COUNT(*) FROM heroes").fetchone()[0]
    cur = conn.execute(
        """INSERT INTO heroes (name, class, color, max_hp, current_hp, sort_order)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, hero_class, color, max_hp, max_hp, sort_order),
    )
    return cur.lastrowid


def update_hero(conn, hero_id: int, **kwargs) -> None:
    allowed = {"name", "color", "max_hp", "current_hp", "xp", "level",
                "coins", "is_knocked_out", "knockout_until", "sort_order"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE heroes SET {set_clause} WHERE id = ?",
        (*fields.values(), hero_id),
    )


def delete_hero(conn, hero_id: int) -> None:
    # Null out non-cascade FKs before deleting
    conn.execute("UPDATE events SET hero_id = NULL WHERE hero_id = ?", (hero_id,))
    conn.execute("UPDATE reward_claims SET hero_id = NULL WHERE hero_id = ?", (hero_id,))
    conn.execute("DELETE FROM heroes WHERE id = ?", (hero_id,))


# ── Task Templates ─────────────────────────────────────────────────────────────

def get_all_templates(conn) -> List[sqlite3.Row]:
    """Returns all templates (active AND inactive) joined with hero info."""
    return conn.execute(
        """SELECT t.*, h.name AS hero_name, h.color AS hero_color,
                  h.class AS hero_class
           FROM task_templates t
           JOIN heroes h ON h.id = t.hero_id
           ORDER BY h.sort_order, t.id"""
    ).fetchall()


def get_active_templates(conn) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM task_templates WHERE is_active = 1"
    ).fetchall()


def create_template(conn, hero_id: int, title: str, description: str,
                    difficulty: str, xp_reward: int, coin_reward: int,
                    boss_damage: int, miss_damage: int) -> int:
    cur = conn.execute(
        """INSERT INTO task_templates
           (hero_id, title, description, difficulty, xp_reward, coin_reward,
            boss_damage, miss_damage)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (hero_id, title, description, difficulty, xp_reward, coin_reward,
         boss_damage, miss_damage),
    )
    return cur.lastrowid


def toggle_template(conn, template_id: int) -> None:
    conn.execute(
        "UPDATE task_templates SET is_active = NOT is_active WHERE id = ?",
        (template_id,)
    )


def delete_template(conn, template_id: int) -> None:
    conn.execute("DELETE FROM task_templates WHERE id = ?", (template_id,))


# ── Daily Tasks ────────────────────────────────────────────────────────────────

def get_tasks_for_date(conn, task_date: str) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, h.name AS hero_name, h.color AS hero_color,
                  h.class AS hero_class
           FROM tasks t
           JOIN heroes h ON h.id = t.hero_id
           WHERE t.task_date = ?
           ORDER BY h.sort_order, t.id""",
        (task_date,),
    ).fetchall()


def get_tasks_for_hero_date(conn, hero_id: int, task_date: str) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tasks WHERE hero_id = ? AND task_date = ? ORDER BY id",
        (hero_id, task_date),
    ).fetchall()


def get_task(conn, task_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, h.name AS hero_name, h.color AS hero_color,
                  h.class AS hero_class
           FROM tasks t JOIN heroes h ON h.id = t.hero_id
           WHERE t.id = ?""",
        (task_id,)
    ).fetchone()


def tasks_already_generated(conn, task_date: str) -> bool:
    count = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE task_date = ?", (task_date,)
    ).fetchone()[0]
    return count > 0


def generate_daily_tasks(conn, task_date: str) -> int:
    templates = get_active_templates(conn)
    count = 0
    for tmpl in templates:
        conn.execute(
            """INSERT INTO tasks
               (hero_id, template_id, title, description, difficulty,
                xp_reward, coin_reward, boss_damage, miss_damage, task_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tmpl["hero_id"], tmpl["id"], tmpl["title"], tmpl["description"],
             tmpl["difficulty"], tmpl["xp_reward"], tmpl["coin_reward"],
             tmpl["boss_damage"], tmpl["miss_damage"], task_date),
        )
        count += 1
    return count


def update_task_state(conn, task_id: int, state: str,
                      timestamp_field: Optional[str] = None) -> None:
    now = datetime.now().isoformat()
    if timestamp_field:
        conn.execute(
            f"UPDATE tasks SET state = ?, {timestamp_field} = ? WHERE id = ?",
            (state, now, task_id),
        )
    else:
        conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (state, task_id))


def create_one_off_task(conn, hero_id: int, title: str, description: str,
                        difficulty: str, task_date: str) -> int:
    from config import TASK_DIFFICULTY
    diff = TASK_DIFFICULTY.get(difficulty, TASK_DIFFICULTY["medium"])
    cur = conn.execute(
        """INSERT INTO tasks
           (hero_id, title, description, difficulty,
            xp_reward, coin_reward, boss_damage, miss_damage, task_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (hero_id, title, description, difficulty,
         diff["xp"], diff["coins"], diff["boss_damage"], diff["miss_damage"],
         task_date),
    )
    return cur.lastrowid


# ── Boss ───────────────────────────────────────────────────────────────────────

def get_active_boss(conn) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM bosses WHERE is_defeated = 0 ORDER BY id DESC LIMIT 1"
    ).fetchone()


def get_latest_boss(conn) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM bosses ORDER BY id DESC LIMIT 1"
    ).fetchone()


def create_boss(conn, name: str, image_key: str, lore: str, color: str,
                max_hp: int, week_number: int,
                week_start: str, week_end: str) -> int:
    cur = conn.execute(
        """INSERT INTO bosses (name, image_key, lore, color, max_hp, current_hp,
           week_number, week_start, week_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, image_key, lore, color, max_hp, max_hp,
         week_number, week_start, week_end),
    )
    return cur.lastrowid


def damage_boss(conn, boss_id: int, damage: int) -> Dict[str, Any]:
    boss = conn.execute("SELECT * FROM bosses WHERE id = ?", (boss_id,)).fetchone()
    new_hp = max(0, boss["current_hp"] - damage)
    defeated = new_hp <= 0
    now = datetime.now().isoformat()
    conn.execute(
        """UPDATE bosses SET current_hp = ?, is_defeated = ?,
           defeated_at = CASE WHEN ? THEN ? ELSE defeated_at END
           WHERE id = ?""",
        (new_hp, 1 if defeated else 0, defeated, now, boss_id),
    )
    return {"new_hp": new_hp, "max_hp": boss["max_hp"], "defeated": defeated}


# ── Events ─────────────────────────────────────────────────────────────────────

def log_event(conn, event_type: str, message: str,
              hero_id: Optional[int] = None,
              metadata: Optional[Dict] = None) -> None:
    conn.execute(
        "INSERT INTO events (event_type, hero_id, message, metadata) VALUES (?, ?, ?, ?)",
        (event_type, hero_id, message,
         json.dumps(metadata) if metadata else None),
    )


def get_recent_events(conn, limit: int = 30) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT e.*, h.name AS hero_name, h.color AS hero_color
           FROM events e
           LEFT JOIN heroes h ON h.id = e.hero_id
           ORDER BY e.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()


def get_events_filtered(conn, event_type: Optional[str] = None,
                        limit: int = 50, offset: int = 0) -> List[sqlite3.Row]:
    if event_type:
        rows = conn.execute(
            """SELECT e.*, h.name AS hero_name, h.color AS hero_color
               FROM events e
               LEFT JOIN heroes h ON h.id = e.hero_id
               WHERE e.event_type = ?
               ORDER BY e.id DESC LIMIT ? OFFSET ?""",
            (event_type, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT e.*, h.name AS hero_name, h.color AS hero_color
               FROM events e
               LEFT JOIN heroes h ON h.id = e.hero_id
               ORDER BY e.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return rows


# ── Rewards ────────────────────────────────────────────────────────────────────

def get_all_rewards(conn) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM rewards ORDER BY is_family_reward DESC, created_at DESC"
    ).fetchall()


def create_reward(conn, name: str, description: str,
                  cost_coins: int, is_family_reward: bool) -> int:
    cur = conn.execute(
        """INSERT INTO rewards (name, description, cost_coins, is_family_reward)
           VALUES (?, ?, ?, ?)""",
        (name, description, cost_coins, 1 if is_family_reward else 0),
    )
    return cur.lastrowid


def toggle_reward(conn, reward_id: int) -> None:
    conn.execute(
        "UPDATE rewards SET is_active = NOT is_active WHERE id = ?", (reward_id,)
    )


def delete_reward(conn, reward_id: int) -> None:
    conn.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))


def claim_reward(conn, reward_id: int, hero_id: Optional[int] = None) -> Optional[sqlite3.Row]:
    reward = conn.execute(
        "SELECT * FROM rewards WHERE id = ? AND is_active = 1", (reward_id,)
    ).fetchone()
    if not reward:
        return None
    conn.execute(
        """INSERT INTO reward_claims (reward_id, hero_id, cost_coins)
           VALUES (?, ?, ?)""",
        (reward_id, hero_id, reward["cost_coins"]),
    )
    return reward


def get_claim_history(conn, limit: int = 20) -> List[sqlite3.Row]:
    return conn.execute(
        """SELECT rc.*, r.name AS reward_name, h.name AS hero_name
           FROM reward_claims rc
           JOIN rewards r ON r.id = rc.reward_id
           LEFT JOIN heroes h ON h.id = rc.hero_id
           ORDER BY rc.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()


def fulfill_claim(conn, claim_id: int) -> None:
    conn.execute(
        """UPDATE reward_claims SET is_fulfilled = 1, fulfilled_at = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), claim_id),
    )
