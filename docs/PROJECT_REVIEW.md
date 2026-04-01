# Project Review & Improvement Plan

## Overall impression
Family Quest has a clean separation of concerns:
- `app.py` handles web routing and orchestration.
- `game_logic.py` centralizes game mechanics.
- `db.py` encapsulates storage concerns.

That structure is a great base for scaling this into a longer-lived app.

---

## High-priority improvements

### 1) Add authentication for admin routes
**Why:** All `/admin/*` routes are currently open.

**Suggested approach:**
- Add a simple auth layer first (shared admin passcode in environment variables).
- Move toward user accounts/sessions later if needed.
- At minimum, block state-changing POST routes for unauthenticated users.

---

### 2) Move scheduler lifecycle into FastAPI lifespan
**Why:** `@app.on_event("startup")` is deprecated in modern FastAPI patterns, and explicit lifespan management gives cleaner startup/shutdown behavior.

**Suggested approach:**
- Use an async lifespan context manager.
- Start APScheduler in lifespan startup and stop it in lifespan shutdown.
- Keep existing job functions intact.

---

### 3) Add automated tests for game rules
**Why:** Core RPG calculations are deterministic and ideal for test coverage.

**Suggested approach:**
- Add `pytest` and create unit tests for:
  - XP/level boundaries
  - class passives (mage/rogue/healer/ranger/warrior)
  - KO/recovery behavior
  - end-of-day missed-task handling
- Add a small integration test for the approve-task flow.

---

## Medium-priority improvements

### 4) Tighten DB integrity constraints
**Why:** SQLite schema currently allows broad text values for some columns.

**Suggested approach:**
- Add CHECK constraints for enumerations (`tasks.state`, difficulty values).
- Add useful indexes:
  - `tasks(task_date, state)`
  - `events(created_at)`
  - `heroes(sort_order)`

---

### 5) Improve observability and operations
**Why:** Debugging and maintenance are easier with structured logs and health checks.

**Suggested approach:**
- Add `/healthz` endpoint.
- Switch key events from print-style behavior to `logging` with levels.
- Capture scheduler errors with explicit logging and retries.

---

### 6) Add backup/export workflow
**Why:** This app stores ongoing family progress in a local SQLite file.

**Suggested approach:**
- Add admin action for JSON export (heroes/tasks/rewards/events).
- Add documented backup command (copy sqlite file + timestamp).
- Optionally add import/restore with validation.

---

## Low-priority product improvements

### 7) UX polish
- Add confirmation modals for destructive actions (delete hero/template/reward).
- Add visual indicator when a hero is KO’d and rewards are paused.
- Add clearer admin task filters (pending/completed/missed/all).

### 8) Balance tooling
- Add a simple “simulation” script to run many virtual days and inspect economy progression.
- Use this to tune XP/coins/boss HP values in `config.py`.

---

## Suggested roadmap
1. Security baseline (admin auth)
2. Test suite for core mechanics
3. Lifespan scheduler migration
4. DB constraints + indexes
5. Ops features (health/logging/backup)

This order reduces risk first, then improves maintainability and long-term reliability.
