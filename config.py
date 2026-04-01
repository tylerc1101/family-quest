"""
config.py — Game balance constants, boss roster, hero classes.
All tunable values live here so they're easy to adjust without
touching game logic. Think of this as your game designer's spreadsheet.
"""

from typing import Dict, Any

# ── Leveling ──────────────────────────────────────────────────────────────────

MAX_LEVEL = 50
# XP required to reach level N = int(XP_BASE * (N - 1) ** XP_EXPONENT)
XP_BASE = 100
XP_EXPONENT = 1.4

# ── Hero Base Stats by Class ───────────────────────────────────────────────────

HERO_BASE_HP: Dict[str, int] = {
    "warrior": 160,
    "mage":     90,
    "rogue":   110,
    "healer":  100,
    "ranger":  130,
}

HERO_HP_PER_LEVEL: Dict[str, int] = {
    "warrior": 18,
    "mage":     8,
    "rogue":   11,
    "healer":  10,
    "ranger":  13,
}

# ── Hero Classes ───────────────────────────────────────────────────────────────
# 'passive' is checked in game_logic.py — easy to extend.

HERO_CLASSES: Dict[str, Dict[str, Any]] = {
    "warrior": {"label": "Warrior", "emoji": "⚔️", "passive": "boss_damage_bonus", "boss_damage_bonus": 1.25},
    "mage":    {"label": "Mage",    "emoji": "🔮", "passive": "xp_bonus",         "xp_bonus": 1.30},
    "rogue":   {"label": "Rogue",   "emoji": "🗡️", "passive": "coin_bonus",       "coin_bonus": 1.50},
    "healer":  {"label": "Healer",  "emoji": "💚", "passive": "party_heal",       "party_heal": 3},
    "ranger":  {"label": "Ranger",  "emoji": "🏹", "passive": "crit_chance",      "crit_chance": 0.20},
}

# ── Task Difficulty Presets ────────────────────────────────────────────────────

TASK_DIFFICULTY: Dict[str, Dict[str, int]] = {
    "easy":   {"xp": 10,  "coins": 5,   "boss_damage": 20,  "miss_damage": 8},
    "medium": {"xp": 25,  "coins": 12,  "boss_damage": 50,  "miss_damage": 20},
    "hard":   {"xp": 50,  "coins": 25,  "boss_damage": 100, "miss_damage": 40},
    "epic":   {"xp": 100, "coins": 50,  "boss_damage": 200, "miss_damage": 80},
}

# ── Knockout System ────────────────────────────────────────────────────────────

KNOCKOUT_DURATION_HOURS = 6   # How long a KO'd hero cannot earn rewards
LEVELUP_HEAL_PERCENT   = 0.20  # Fraction of max HP restored on level-up

# ── Family Bonus ───────────────────────────────────────────────────────────────

BOSS_DEFEAT_BONUS_COINS = 150  # Extra coins per hero when boss is defeated

# ── Boss Roster ────────────────────────────────────────────────────────────────
# Bosses rotate weekly. Add more objects to this list to expand the roster.

BOSS_ROSTER = [
    {
        "name": "The Laundry Golem",
        "image_key": "laundry_golem",
        "max_hp": 800,
        "color": "#8B5E3C",
        "lore": "Forged from unfolded socks and forgotten permission slips.",
        "flavor_attack": "hurls a pile of unsorted laundry!",
    },
    {
        "name": "Dustmaw the Untidy",
        "image_key": "dustmaw",
        "max_hp": 1000,
        "color": "#6B6B6B",
        "lore": "A creature of pure entropy. It grows stronger with every ignored mess.",
        "flavor_attack": "exhales a cloud of forgotten crumbs!",
    },
    {
        "name": "The Homework Hydra",
        "image_key": "homework_hydra",
        "max_hp": 1200,
        "color": "#4B0082",
        "lore": "Complete one assignment and two more appear — unless you're faster.",
        "flavor_attack": "assigns three surprise worksheets!",
    },
    {
        "name": "Bedtime Basilisk",
        "image_key": "bedtime_basilisk",
        "max_hp": 700,
        "color": "#2F4F4F",
        "lore": "Turns children to stone if they stay up past 9 PM.",
        "flavor_attack": "fixes you with its sleepy gaze!",
    },
    {
        "name": "Lord Clutter",
        "image_key": "lord_clutter",
        "max_hp": 1500,
        "color": "#8B0000",
        "lore": "The final form of household chaos. This one is personal.",
        "flavor_attack": "summons a wave of misplaced belongings!",
    },
]

# ── Hero Color Palette ─────────────────────────────────────────────────────────
# Offered as choices during hero creation.

HERO_COLORS = [
    {"hex": "#e74c3c", "name": "Crimson"},
    {"hex": "#3498db", "name": "Azure"},
    {"hex": "#2ecc71", "name": "Emerald"},
    {"hex": "#f39c12", "name": "Gold"},
    {"hex": "#9b59b6", "name": "Violet"},
    {"hex": "#1abc9c", "name": "Teal"},
    {"hex": "#e67e22", "name": "Amber"},
    {"hex": "#e91e63", "name": "Rose"},
    {"hex": "#00bcd4", "name": "Cyan"},
    {"hex": "#ff5722", "name": "Ember"},
]
