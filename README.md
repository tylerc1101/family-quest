# Family Quest

A lightweight FastAPI app that turns household tasks into a cooperative RPG.
Heroes complete tasks, earn XP/coins, and damage a rotating weekly boss.

## Features
- **Hero progression**: classes, levels, XP curve, class passives, HP/KO states.
- **Task lifecycle**: template-driven task generation, hero submission, admin approval/rejection.
- **Boss battles**: weekly bosses with HP, class-based damage effects, defeat rewards.
- **Rewards economy**: coin spending + claim/fulfillment workflow.
- **Adventure log**: filterable event history and activity feed.
- **Automations**: scheduled end-of-day processing and KO recovery checks.

## Tech stack
- FastAPI + Jinja2 templates
- SQLite (WAL mode)
- APScheduler (background jobs)
- HTMX for partial refreshes

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh --reload
```

Then open:
- Dashboard: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin`
- Adventure log: `http://127.0.0.1:8000/log`

## Useful commands
```bash
# Start app
./run.sh

# Start app with auto-reload
./run.sh --reload

# Basic syntax check
python3 -m py_compile app.py game_logic.py db.py config.py
```

## Project layout
- `app.py` — route handlers, template rendering, scheduler startup/jobs.
- `game_logic.py` — game rules and state transitions.
- `db.py` — schema and data-access layer.
- `config.py` — tunable balancing constants.
- `templates/` — pages and HTMX partials.
- `static/` — CSS and JS assets.

## Notes
- Data is stored locally in `family_quest.db`.
- The app currently has no authentication/authorization; `/admin` is open by default.
