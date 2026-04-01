"""
app.py — FastAPI routes, startup, APScheduler.
"""

from datetime import date
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

import config
import db
import game_logic

# ── App Setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Family Quest")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Expose helpers to Jinja2
templates.env.globals["xp_progress_pct"] = game_logic.xp_progress_pct
templates.env.globals["hp_pct"] = game_logic.hp_pct
templates.env.globals["hp_color_class"] = game_logic.hp_color_class
templates.env.globals["xp_to_next_level"] = game_logic.xp_to_next_level
templates.env.globals["level_for_xp"] = game_logic.level_for_xp
templates.env.globals["HERO_CLASSES"] = config.HERO_CLASSES
templates.env.globals["HERO_COLORS"] = config.HERO_COLORS
templates.env.globals["TASK_DIFFICULTY"] = config.TASK_DIFFICULTY
templates.env.globals["BOSS_ROSTER"] = config.BOSS_ROSTER


@app.on_event("startup")
def startup():
    db.init_db()
    today = date.today().isoformat()
    with db.get_db() as conn:
        if not db.tasks_already_generated(conn, today):
            count = db.generate_daily_tasks(conn, today)
            if count:
                db.log_event(conn, "system",
                             f"⚙️ Auto-generated {count} tasks for {today}")
        game_logic.check_and_recover_knockouts(conn)

    scheduler = BackgroundScheduler()
    scheduler.add_job(_nightly_job, "cron", hour=23, minute=59)
    scheduler.add_job(_recovery_job, "interval", minutes=30)
    scheduler.start()


def _nightly_job():
    with db.get_db() as conn:
        game_logic.process_end_of_day(conn)
    today = date.today().isoformat()
    with db.get_db() as conn:
        count = db.generate_daily_tasks(conn, today)
        if count:
            db.log_event(conn, "system", f"⚙️ Auto-generated {count} tasks for {today}")


def _recovery_job():
    with db.get_db() as conn:
        game_logic.check_and_recover_knockouts(conn)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _render(request: Request, template: str, ctx: dict) -> HTMLResponse:
    ctx.setdefault("today", _today())
    ctx.setdefault("msg", "")
    ctx.setdefault("flash_type", "success")
    return templates.TemplateResponse(request=request, name=template, context=ctx)


def _redir(path: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(path, status_code=status_code)


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with db.get_db() as conn:
        heroes = db.get_all_heroes(conn)
        boss = db.get_active_boss(conn) or db.get_latest_boss(conn)
        events = db.get_recent_events(conn, 20)
        today = _today()
        all_tasks = db.get_tasks_for_date(conn, today)
        tasks_by_hero: dict = {}
        for task in all_tasks:
            tasks_by_hero.setdefault(task["hero_id"], []).append(task)
    return _render(request, "dashboard.html", {
        "heroes": heroes, "boss": boss,
        "events": events, "tasks_by_hero": tasks_by_hero,
    })


# ── HTMX Partials ─────────────────────────────────────────────────────────────

@app.get("/partials/heroes", response_class=HTMLResponse)
def partial_heroes(request: Request):
    with db.get_db() as conn:
        heroes = db.get_all_heroes(conn)
        today = _today()
        all_tasks = db.get_tasks_for_date(conn, today)
        tasks_by_hero: dict = {}
        for task in all_tasks:
            tasks_by_hero.setdefault(task["hero_id"], []).append(task)
    return _render(request, "partials/heroes.html",
                   {"heroes": heroes, "tasks_by_hero": tasks_by_hero})


@app.get("/partials/boss", response_class=HTMLResponse)
def partial_boss(request: Request):
    with db.get_db() as conn:
        boss = db.get_active_boss(conn) or db.get_latest_boss(conn)
        heroes = db.get_all_heroes(conn)
    return _render(request, "partials/boss_scene.html", {"boss": boss, "heroes": heroes})


@app.get("/partials/events", response_class=HTMLResponse)
def partial_events(request: Request):
    with db.get_db() as conn:
        events = db.get_recent_events(conn, 25)
    return _render(request, "partials/event_feed.html", {"events": events})


# ── Hero Personal Screen ───────────────────────────────────────────────────────

@app.get("/hero/{hero_id}", response_class=HTMLResponse)
def hero_screen(request: Request, hero_id: int, msg: str = ""):
    with db.get_db() as conn:
        hero = db.get_hero(conn, hero_id)
        if not hero:
            return HTMLResponse("Hero not found", status_code=404)
        tasks = db.get_tasks_for_hero_date(conn, hero_id, _today())
    xp_pct = game_logic.xp_progress_pct(hero["xp"])
    xp_to_next = game_logic.xp_to_next_level(hero["xp"])
    return _render(request, "hero_screen.html",
                   {"hero": hero, "tasks": tasks,
                    "xp_pct": xp_pct, "xp_to_next": xp_to_next, "msg": msg})


@app.post("/hero/{hero_id}/task/{task_id}/complete")
def hero_complete_task(hero_id: int, task_id: int):
    with db.get_db() as conn:
        task = db.get_task(conn, task_id)
        if not task or task["hero_id"] != hero_id or task["state"] != "pending":
            return _redir(f"/hero/{hero_id}")
        db.update_task_state(conn, task_id, "completed", "completed_at")
        hero = db.get_hero(conn, hero_id)
        damage_result = game_logic.apply_task_boss_damage(conn, hero, task)
        db.log_event(conn, "task_completed",
                     f"📋 {hero['name']} submitted '{task['title']}' — awaiting approval.",
                     hero_id)
    msg = "Task+submitted+for+approval!"
    if damage_result["applied"]:
        msg = f"Task+submitted!+Boss+took+{damage_result['damage']}+damage!"
    return _redir(f"/hero/{hero_id}?msg={msg}")


# ── Admin — Overview ──────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_index(request: Request, msg: str = ""):
    with db.get_db() as conn:
        heroes = db.get_all_heroes(conn)
        boss = db.get_active_boss(conn) or db.get_latest_boss(conn)
        tasks = db.get_tasks_for_date(conn, _today())
        pending_tasks = [t for t in tasks if t["state"] == "completed"]
        ko_count = sum(1 for h in heroes if h["is_knocked_out"])
    return _render(request, "admin/index.html", {
        "admin_page": "overview",
        "heroes": heroes, "boss": boss,
        "pending_tasks": pending_tasks, "ko_count": ko_count, "msg": msg,
    })


# ── Admin — Heroes ────────────────────────────────────────────────────────────

@app.get("/admin/heroes", response_class=HTMLResponse)
def admin_heroes(request: Request, msg: str = ""):
    with db.get_db() as conn:
        heroes = db.get_all_heroes(conn)
    return _render(request, "admin/heroes.html",
                   {"admin_page": "heroes", "heroes": heroes, "msg": msg})


@app.post("/admin/heroes")
def admin_create_hero(
    name: str = Form(...),
    hero_class: str = Form(...),
    color: str = Form(...),
):
    if hero_class not in config.HERO_CLASSES:
        return _redir("/admin/heroes?msg=Invalid+class.")
    with db.get_db() as conn:
        hero_id = db.create_hero(conn, name.strip(), hero_class, color)
        cls_label = config.HERO_CLASSES[hero_class]["label"]
        db.log_event(conn, "hero_created",
                     f"🌟 {name} the {cls_label} has joined the party!", hero_id)
    return _redir("/admin/heroes?msg=Hero+created!")


@app.post("/admin/heroes/{hero_id}/delete")
def admin_delete_hero(hero_id: int):
    with db.get_db() as conn:
        hero = db.get_hero(conn, hero_id)
        if hero:
            db.delete_hero(conn, hero_id)
            db.log_event(conn, "hero_removed", f"👋 {hero['name']} has left the party.")
    return _redir("/admin/heroes?msg=Hero+removed.")


@app.post("/admin/heroes/{hero_id}/heal")
def admin_heal_hero(hero_id: int):
    with db.get_db() as conn:
        hero = db.get_hero(conn, hero_id)
        if hero:
            db.update_hero(conn, hero_id,
                           current_hp=hero["max_hp"],
                           is_knocked_out=0, knockout_until=None)
            db.log_event(conn, "admin_heal",
                         f"💊 Admin fully healed {hero['name']}.", hero_id)
    return _redir("/admin/heroes?msg=Hero+healed!")


# ── Admin — Task Templates ────────────────────────────────────────────────────

@app.get("/admin/templates", response_class=HTMLResponse)
def admin_templates(request: Request, msg: str = ""):
    with db.get_db() as conn:
        tmpl_list = db.get_all_templates(conn)
        heroes = db.get_all_heroes(conn)
    return _render(request, "admin/templates.html",
                   {"admin_page": "templates",
                    "templates": tmpl_list, "heroes": heroes, "msg": msg})


@app.post("/admin/templates")
def admin_create_template(
    hero_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    difficulty: str = Form("medium"),
):
    diff = config.TASK_DIFFICULTY.get(difficulty, config.TASK_DIFFICULTY["medium"])
    with db.get_db() as conn:
        db.create_template(conn, hero_id, name.strip(), description, difficulty,
                           diff["xp"], diff["coins"],
                           diff["boss_damage"], diff["miss_damage"])
    return _redir("/admin/templates?msg=Template+created!")


@app.post("/admin/templates/{tmpl_id}/toggle")
def admin_toggle_template(tmpl_id: int):
    with db.get_db() as conn:
        db.toggle_template(conn, tmpl_id)
    return _redir("/admin/templates?msg=Template+updated.")


@app.post("/admin/templates/{tmpl_id}/delete")
def admin_delete_template(tmpl_id: int):
    with db.get_db() as conn:
        db.delete_template(conn, tmpl_id)
    return _redir("/admin/templates?msg=Template+deleted.")


# ── Admin — Today's Tasks ─────────────────────────────────────────────────────

@app.get("/admin/tasks", response_class=HTMLResponse)
def admin_tasks(request: Request, msg: str = ""):
    today = _today()
    with db.get_db() as conn:
        tasks = db.get_tasks_for_date(conn, today)
        heroes = db.get_all_heroes(conn)
    return _render(request, "admin/tasks.html",
                   {"admin_page": "tasks",
                    "tasks": tasks, "heroes": heroes, "msg": msg})


@app.post("/admin/tasks/generate")
def admin_generate_tasks():
    today = _today()
    with db.get_db() as conn:
        if db.tasks_already_generated(conn, today):
            return _redir("/admin/tasks?msg=Tasks+already+generated+for+today.")
        count = db.generate_daily_tasks(conn, today)
        db.log_event(conn, "system", f"⚙️ Admin generated {count} tasks for {today}")
    return _redir(f"/admin/tasks?msg=Generated+{count}+tasks!")


@app.post("/admin/tasks")
def admin_create_one_off(
    hero_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    difficulty: str = Form("medium"),
):
    with db.get_db() as conn:
        db.create_one_off_task(conn, hero_id, name.strip(), description,
                               difficulty, _today())
    return _redir("/admin/tasks?msg=Task+added!")


@app.post("/admin/tasks/{task_id}/approve")
def admin_approve_task(task_id: int):
    with db.get_db() as conn:
        game_logic.approve_task(conn, task_id)
    return _redir("/admin?msg=Task+approved!")


@app.post("/admin/tasks/{task_id}/reject")
def admin_reject_task(task_id: int):
    with db.get_db() as conn:
        task = db.get_task(conn, task_id)
        if task and task["state"] == "completed":
            db.update_task_state(conn, task_id, "pending")
            hero = db.get_hero(conn, task["hero_id"])
            db.log_event(conn, "task_rejected",
                         f"❌ Admin sent '{task['title']}' back to {hero['name']}.",
                         task["hero_id"])
    return _redir("/admin?msg=Task+sent+back.")


@app.post("/admin/tasks/approve-all")
def admin_approve_all():
    today = _today()
    with db.get_db() as conn:
        tasks = db.get_tasks_for_date(conn, today)
        count = 0
        for task in tasks:
            if task["state"] == "completed":
                game_logic.approve_task(conn, task["id"])
                count += 1
    return _redir(f"/admin/tasks?msg=Approved+{count}+tasks!")


# ── Admin — Boss ──────────────────────────────────────────────────────────────

@app.get("/admin/boss", response_class=HTMLResponse)
def admin_boss(request: Request, msg: str = ""):
    with db.get_db() as conn:
        boss = db.get_active_boss(conn) or db.get_latest_boss(conn)
    return _render(request, "admin/boss.html",
                   {"admin_page": "boss",
                    "boss": boss,
                    "boss_roster": config.BOSS_ROSTER,
                    "msg": msg})


@app.post("/admin/boss/spawn")
def admin_spawn_boss():
    with db.get_db() as conn:
        game_logic.spawn_next_boss(conn)
        boss = db.get_latest_boss(conn)
        db.log_event(conn, "boss_spawn",
                     f"💀 {boss['name']} has appeared! The battle begins!")
    return _redir("/admin/boss?msg=New+boss+spawned!")


@app.post("/admin/boss/damage")
def admin_test_damage():
    """Dev helper: deal 50 test damage to the active boss."""
    with db.get_db() as conn:
        boss = db.get_active_boss(conn)
        if boss:
            db.damage_boss(conn, boss["id"], 50)
            db.log_event(conn, "boss_damaged",
                         "🧪 Test damage: 50 HP dealt to boss.")
    return _redir("/admin/boss?msg=Test+damage+applied.")


# ── Admin — End of Day ────────────────────────────────────────────────────────

@app.post("/admin/end-of-day")
def admin_end_of_day():
    with db.get_db() as conn:
        summary = game_logic.process_end_of_day(conn)
    missed = len(summary.get("missed", []))
    return _redir(f"/admin?msg=End-of-day+done.+{missed}+task(s)+missed.")


# ── Admin — Rewards ───────────────────────────────────────────────────────────

@app.get("/admin/rewards", response_class=HTMLResponse)
def admin_rewards(request: Request, msg: str = ""):
    with db.get_db() as conn:
        rewards = db.get_all_rewards(conn)
        claim_history = db.get_claim_history(conn, 20)
        heroes = db.get_all_heroes(conn)
    return _render(request, "admin/rewards.html",
                   {"admin_page": "rewards",
                    "rewards": rewards, "claim_history": claim_history,
                    "heroes": heroes, "msg": msg})


@app.post("/admin/rewards")
def admin_create_reward(
    name: str = Form(...),
    description: str = Form(""),
    cost_coins: int = Form(0),
    is_family_reward: str = Form(""),
):
    with db.get_db() as conn:
        db.create_reward(conn, name.strip(), description,
                         cost_coins, bool(is_family_reward))
    return _redir("/admin/rewards?msg=Reward+added!")


@app.post("/admin/rewards/{reward_id}/toggle")
def admin_toggle_reward(reward_id: int):
    with db.get_db() as conn:
        db.toggle_reward(conn, reward_id)
    return _redir("/admin/rewards?msg=Reward+updated.")


@app.post("/admin/rewards/{reward_id}/delete")
def admin_delete_reward(reward_id: int):
    with db.get_db() as conn:
        db.delete_reward(conn, reward_id)
    return _redir("/admin/rewards?msg=Reward+deleted.")


@app.post("/admin/rewards/claims/{claim_id}/fulfill")
def admin_fulfill_claim(claim_id: int):
    with db.get_db() as conn:
        db.fulfill_claim(conn, claim_id)
    return _redir("/admin/rewards?msg=Claim+fulfilled!")


# ── Adventure Log ─────────────────────────────────────────────────────────────

@app.get("/log", response_class=HTMLResponse)
def adventure_log(request: Request, page: int = 1,
                  type: Optional[str] = None):
    page_size = 50
    offset = (page - 1) * page_size
    with db.get_db() as conn:
        events = db.get_events_filtered(conn, event_type=type,
                                        limit=page_size + 1, offset=offset)
    has_next = len(events) > page_size
    return _render(request, "log.html", {
        "events": events[:page_size],
        "page": page,
        "has_next": has_next,
        "active_filter": type,
    })
