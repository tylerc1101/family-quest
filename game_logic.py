"""
game_logic.py — Pure game mechanics. Functions take a db connection + args
and return plain dicts. Side effects are limited to DB writes + event logs.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import config
import db


# ── XP / Levelling ─────────────────────────────────────────────────────────────

def xp_for_level(level: int) -> int:
    """Total XP required to reach `level`."""
    if level <= 1:
        return 0
    return int(config.XP_BASE * (level - 1) ** config.XP_EXPONENT)


def level_for_xp(xp: int) -> int:
    lvl = 1
    while lvl < config.MAX_LEVEL and xp >= xp_for_level(lvl + 1):
        lvl += 1
    return lvl


def xp_progress_pct(xp_or_hero) -> float:
    xp = xp_or_hero["xp"] if hasattr(xp_or_hero, "__getitem__") else int(xp_or_hero)
    lvl = level_for_xp(xp)
    if lvl >= config.MAX_LEVEL:
        return 100.0
    current_floor = xp_for_level(lvl)
    next_ceil = xp_for_level(lvl + 1)
    if next_ceil == current_floor:
        return 100.0
    return round((xp - current_floor) / (next_ceil - current_floor) * 100, 1)


def xp_to_next_level(xp_or_hero, _ignored=None) -> int:
    """Accept (hero_row) or (level, xp) for backward compat with templates."""
    if _ignored is not None:
        xp = int(_ignored)  # called as xp_to_next_level(hero.level, hero.xp)
    elif hasattr(xp_or_hero, "__getitem__"):
        xp = xp_or_hero["xp"]
    else:
        xp = int(xp_or_hero)
    lvl = level_for_xp(xp)
    if lvl >= config.MAX_LEVEL:
        return 0
    return xp_for_level(lvl + 1) - xp


# ── Damage Calculations ────────────────────────────────────────────────────────

def calculate_boss_damage(hero, task) -> Dict[str, Any]:
    """Returns dict with damage, is_crit."""
    base = task["boss_damage"]
    hero_class = hero["hero_class"]
    passive = config.HERO_CLASSES.get(hero_class, {})

    damage = base
    is_crit = False

    if hero_class == "warrior":
        damage = int(damage * passive.get("boss_damage_bonus", 1.25))
    elif hero_class == "ranger":
        if random.random() < passive.get("crit_chance", 0.20):
            damage *= 2
            is_crit = True

    return {"damage": damage, "is_crit": is_crit}


def calculate_xp_reward(hero, task) -> int:
    base = task["xp_reward"]
    passive = config.HERO_CLASSES.get(hero["hero_class"], {})
    if hero["hero_class"] == "mage":
        return int(base * passive.get("xp_bonus", 1.30))
    return base


def calculate_coin_reward(hero, task) -> int:
    base = task["coin_reward"]
    passive = config.HERO_CLASSES.get(hero["hero_class"], {})
    if hero["hero_class"] == "rogue":
        return int(base * passive.get("coin_bonus", 1.50))
    return base


# ── hp helpers ─────────────────────────────────────────────────────────────────

def hp_pct(hero_or_pct) -> float:
    """Accept a hero Row or a raw float (already a pct)."""
    if isinstance(hero_or_pct, (int, float)):
        return float(hero_or_pct)
    hero = hero_or_pct
    if hero["max_hp"] == 0:
        return 0.0
    return round(hero["current_hp"] / hero["max_hp"] * 100, 1)


def hp_color_class(hero_or_pct) -> str:
    pct = hp_pct(hero_or_pct)
    if pct < 25:
        return "bar-danger"
    if pct < 60:
        return "bar-warn"
    return "bar-safe"


# ── Core Action: Approve Task ──────────────────────────────────────────────────

def approve_task(conn, task_id: int) -> Dict[str, Any]:
    task = db.get_task(conn, task_id)
    if not task or task["state"] not in ("pending", "completed"):
        return {"ok": False, "reason": "invalid_state"}

    hero = db.get_hero(conn, task["hero_id"])
    result: Dict[str, Any] = {"ok": True, "events": []}

    # Mark approved
    db.update_task_state(conn, task_id, "approved", "approved_at")

    # ── Rewards (skip if KO'd) ────────────────────────────────────────────────
    if not hero["is_knocked_out"]:
        xp_gain = calculate_xp_reward(hero, task)
        coin_gain = calculate_coin_reward(hero, task)
        new_xp = hero["xp"] + xp_gain
        new_coins = hero["coins"] + coin_gain
        new_level = level_for_xp(new_xp)
        levelled_up = new_level > hero["level"]

        hp_gain = 0
        if levelled_up:
            from config import HERO_HP_PER_LEVEL, LEVELUP_HEAL_PERCENT
            new_max_hp = (
                config.HERO_BASE_HP.get(hero["hero_class"], 100)
                + (new_level - 1) * HERO_HP_PER_LEVEL.get(hero["hero_class"], 5)
            )
            hp_gain = int(new_max_hp * LEVELUP_HEAL_PERCENT)
            new_hp = min(new_max_hp, hero["current_hp"] + hp_gain)
            db.update_hero(conn, hero["id"],
                           xp=new_xp, level=new_level, coins=new_coins,
                           max_hp=new_max_hp, current_hp=new_hp)
            db.log_event(conn, "level_up",
                         f"⭐ {hero['name']} reached Level {new_level}!",
                         hero["id"])
        else:
            db.update_hero(conn, hero["id"],
                           xp=new_xp, coins=new_coins)

        result["xp_gain"] = xp_gain
        result["coin_gain"] = coin_gain

        # ── Healer passive: party heal ────────────────────────────────────────
        if hero["hero_class"] == "healer":
            heal_amt = config.HERO_CLASSES["healer"].get("party_heal", 3)
            all_heroes = db.get_all_heroes(conn)
            for ally in all_heroes:
                if not ally["is_knocked_out"]:
                    new_hp = min(ally["max_hp"], ally["current_hp"] + heal_amt)
                    db.update_hero(conn, ally["id"], current_hp=new_hp)
            db.log_event(conn, "party_heal",
                         f"💚 {hero['name']}'s healing aura restored {heal_amt} HP to the party!",
                         hero["id"])

    # ── Boss damage ───────────────────────────────────────────────────────────
    boss = db.get_active_boss(conn)
    if boss:
        dmg_result = calculate_boss_damage(hero, task)
        boss_result = db.damage_boss(conn, boss["id"], dmg_result["damage"])

        crit_str = " 💢 CRITICAL HIT!" if dmg_result["is_crit"] else ""
        db.log_event(conn, "boss_damaged",
                     f"⚔️ {hero['name']} dealt {dmg_result['damage']} damage to {boss['name']}!{crit_str}",
                     hero["id"])

        if boss_result["defeated"]:
            db.log_event(conn, "boss_defeated",
                         f"🏆 {boss['name']} has been defeated! The family earns {config.BOSS_DEFEAT_BONUS_COINS} coins!")
        result["boss_damage"] = dmg_result["damage"]
        result["boss_defeated"] = boss_result["defeated"]

    task_label = task["title"]
    ko_note = " (KO'd — rewards paused)" if hero["is_knocked_out"] else ""
    db.log_event(conn, "task_approved",
                 f"✅ {hero['name']} completed '{task_label}'{ko_note}",
                 hero["id"])

    return result


# ── Hero Damage & Knockout ─────────────────────────────────────────────────────

def apply_damage_to_hero(conn, hero_id: int, damage: int, reason: str) -> Dict[str, Any]:
    hero = db.get_hero(conn, hero_id)
    if not hero or hero["is_knocked_out"]:
        return {"ok": False}

    new_hp = max(0, hero["current_hp"] - damage)
    knocked_out = new_hp == 0

    if knocked_out:
        ko_until = (datetime.now() + timedelta(hours=config.KNOCKOUT_DURATION_HOURS)).isoformat()
        db.update_hero(conn, hero_id,
                       current_hp=0, is_knocked_out=1, knockout_until=ko_until)
        db.log_event(conn, "hero_ko",
                     f"😵 {hero['name']} was knocked out! {reason}",
                     hero_id)
    else:
        db.update_hero(conn, hero_id, current_hp=new_hp)

    return {"ok": True, "new_hp": new_hp, "knocked_out": knocked_out}


def check_and_recover_knockouts(conn) -> List[int]:
    """Revive heroes whose KO timer has expired. Returns list of recovered hero IDs."""
    now = datetime.now().isoformat()
    ko_heroes = conn.execute(
        "SELECT * FROM heroes WHERE is_knocked_out = 1 AND knockout_until <= ?",
        (now,)
    ).fetchall()
    recovered = []
    for hero in ko_heroes:
        db.update_hero(conn, hero["id"],
                       is_knocked_out=0, knockout_until=None, current_hp=1)
        db.log_event(conn, "hero_recovered",
                     f"💊 {hero['name']} has recovered and rejoins the fight with 1 HP!",
                     hero["id"])
        recovered.append(hero["id"])
    return recovered


# ── End of Day ─────────────────────────────────────────────────────────────────

def process_end_of_day(conn, task_date: Optional[str] = None) -> Dict[str, Any]:
    from datetime import date as date_cls
    target = task_date or date_cls.today().isoformat()
    pending = conn.execute(
        "SELECT * FROM tasks WHERE task_date = ? AND state = 'pending'",
        (target,)
    ).fetchall()

    missed = []
    for task in pending:
        db.update_task_state(conn, task["id"], "missed")
        hero = db.get_hero(conn, task["hero_id"])
        apply_damage_to_hero(conn, task["hero_id"], task["miss_damage"],
                              f"Missed task: '{task['title']}'")
        db.log_event(conn, "task_missed",
                     f"💀 {hero['name']} missed '{task['title']}' (-{task['miss_damage']} HP)",
                     task["hero_id"])
        missed.append(task["id"])

    return {"missed": missed, "date": target}


# ── Spawn Next Boss ────────────────────────────────────────────────────────────

def spawn_next_boss(conn) -> int:
    from datetime import date as date_cls, timedelta
    latest = db.get_latest_boss(conn)
    week_num = (latest["week_number"] + 1) if latest else 1
    roster_idx = (week_num - 1) % len(config.BOSS_ROSTER)
    boss_cfg = config.BOSS_ROSTER[roster_idx]

    today = date_cls.today()
    week_end = today + timedelta(days=6)

    return db.create_boss(
        conn,
        name=boss_cfg["name"],
        image_key=boss_cfg["image_key"],
        lore=boss_cfg["lore"],
        color=boss_cfg["color"],
        max_hp=boss_cfg["max_hp"],
        week_number=week_num,
        week_start=today.isoformat(),
        week_end=week_end.isoformat(),
    )


# sqlite3.Row doesn't have a type stub so use this for type hints
