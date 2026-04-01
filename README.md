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

## Animated character architecture
- `templates/macros/characters.html` contains the **character actor system**:
  - `character_actor(...)` provides a consistent wrapper DOM for heroes and bosses.
  - State is data-driven through `data-character-state` (`idle`, `attack`, `hit`, `ko`, `victory`).
  - Character effects are separate from art (`fx-arrow`, `fx-slash`, `fx-spell`, `fx-impact`, `fx-glow`).
- `static/css/characters.css` contains reusable animation/state classes.
- `static/js/app.js` triggers state changes during combat (example: ranger attack + boss hit reaction when boss HP drops).

### Adding a new animated character
1. Add a layered macro in `templates/macros/characters.html` using grouped SVG parts:
   - `part-head`, `part-body`, `part-arm-back`, `part-arm-front`, `part-legs`, `part-weapon`.
2. Update `character_actor(...)` to map the new key/class to your macro.
3. Reuse existing state hooks (`data-character-state`) rather than creating one-off CSS.
4. If the character needs a custom effect, add a new `.fx-*` element in the effects layer and style it in `static/css/characters.css`.
5. Keep attack/hit/victory transitions in `static/js/app.js` via `triggerCharacterState(...)`.

## Notes
- Data is stored locally in `family_quest.db`.
- The app currently has no authentication/authorization; `/admin` is open by default.
