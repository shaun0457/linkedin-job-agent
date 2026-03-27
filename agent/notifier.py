"""Telegram Bot: notifications + inline confirm/skip + search config commands."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from agent import config as cfg
from agent import db
from agent import improver

logger = logging.getLogger(__name__)


# ── bot factory ────────────────────────────────────────────────────────────


def build_application(settings: cfg.Settings) -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("retry", cmd_retry))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("set_keywords", cmd_set_keywords))
    app.add_handler(CommandHandler("set_location", cmd_set_location))
    app.add_handler(CommandHandler("set_max", cmd_set_max))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("search_config", cmd_search_config))
    app.add_handler(CommandHandler("set_experience_level", cmd_set_experience_level))
    app.add_handler(CommandHandler("set_blacklist", cmd_set_blacklist))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app


# ── notification helpers ───────────────────────────────────────────────────


async def notify_job(
    app: Application,
    chat_id: str,
    result,  # TailoredResult
) -> None:
    job = result.job
    keywords_text = (
        ", ".join(result.keywords_added[:5]) if result.keywords_added else "—"
    )
    n_kw = len(result.keywords_added)

    text = (
        f"🏢 *{_esc(job.company)}* — {_esc(job.title)}\n"
        f"📍 {_esc(job.location or '—')}\n"
        f"🔗 [View Job]({_esc_url(job.url)})\n\n"
        f"📄 履歷調整重點：\n"
        f"• 新增關鍵字：{_esc(keywords_text)}\n"
        f"• 共調整 {n_kw} 項關鍵字"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 確認", callback_data=f"confirm:{job.job_id}"),
            InlineKeyboardButton("❌ 跳過", callback_data=f"skip:{job.job_id}"),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def notify_error(app: Application, chat_id: str, message: str) -> None:
    await app.bot.send_message(chat_id=chat_id, text=f"⚠️ {message}")


async def notify_run_summary(
    app: Application, chat_id: str, found: int, tailored: int, failed: int
) -> None:
    """Send a run summary after each pipeline execution."""
    text = (
        f"✅ *Run complete*\n"
        f"• 發現新職缺：{found}\n"
        f"• 已客製化：{tailored}\n"
        f"• 失敗：{failed}"
    )
    await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="MarkdownV2",
    )


# ── callback handler ───────────────────────────────────────────────────────


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    settings: cfg.Settings = context.bot_data["settings"]

    if data.startswith("confirm:"):
        job_id = data.removeprefix("confirm:")
        await _handle_confirm(query, settings, job_id)

    elif data.startswith("skip:"):
        job_id = data.removeprefix("skip:")
        await _handle_skip(query, settings, job_id)


async def _handle_confirm(query, settings: cfg.Settings, job_id: str) -> None:
    preview_data = db.get_preview_data(job_id)
    if not preview_data:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ 找不到 preview 資料，請用 /retry " + job_id)
        return

    meta = db.get_job_meta(job_id)
    master_resume_id = meta["master_resume_id"] if meta else None
    if not master_resume_id:
        await query.message.reply_text("⚠️ 找不到 master resume ID，請用 /retry " + job_id)
        return

    confirmed_id = await improver.confirm_resume(
        settings.resume_matcher_url,
        master_resume_id=master_resume_id,
        preview_data=preview_data,
    )
    if not confirmed_id:
        await query.message.reply_text(
            f"⚠️ 確認失敗，請稍後再試 (/retry {job_id})"
        )
        return

    now = datetime.now(timezone.utc).isoformat()
    db.confirm_job(job_id, confirmed_id, now)

    pdf_url = f"{settings.resume_matcher_url}/api/v1/resumes/{confirmed_id}/pdf"
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"✅ 履歷已確認\n📥 下載 PDF → {pdf_url}"
    )


async def _handle_skip(query, settings: cfg.Settings, job_id: str) -> None:
    # No preview resume to delete — RM preview is in-memory only

    now = datetime.now(timezone.utc).isoformat()
    db.skip_job(job_id, now)

    original = query.message.text or ""
    first_line = original.split("\n")[0]
    await query.edit_message_text(
        text=f"~{_esc(first_line)}~ — 已跳過",
        parse_mode="MarkdownV2",
    )


# ── commands ───────────────────────────────────────────────────────────────


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pipeline_fn = context.bot_data.get("run_pipeline")
    if pipeline_fn is None:
        await update.message.reply_text("⚠️ Pipeline 尚未初始化")
        return
    await update.message.reply_text("▶️ 手動觸發搜尋中…")
    asyncio.create_task(pipeline_fn())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    stats = db.get_stats(since=today)
    total = sum(stats.values())
    notified = stats.get("notified", 0)
    confirmed = stats.get("confirmed", 0)
    skipped = stats.get("skipped", 0)

    await update.message.reply_text(
        f"📊 今日統計\n"
        f"• 發現職缺：{total}\n"
        f"• 待決定：{notified}\n"
        f"• 已確認：{confirmed}\n"
        f"• 已跳過：{skipped}"
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: cfg.Settings = context.bot_data["settings"]
    jobs = db.get_recent_confirmed(limit=10)
    if not jobs:
        await update.message.reply_text("尚無已確認的職缺")
        return

    lines = ["📋 最近確認的職缺：\n"]
    for j in jobs:
        pdf_url = f"{settings.resume_matcher_url}/api/v1/resumes/{j['confirmed_resume_id']}/pdf"
        lines.append(f"• {j['title']} @ {j['company']}\n  📥 {pdf_url}")

    await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)


async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法：/retry <job_id>")
        return

    job_id = context.args[0]
    settings: cfg.Settings = context.bot_data["settings"]

    preview_data = db.get_preview_data(job_id)
    if not preview_data:
        await update.message.reply_text(f"找不到 job_id: {job_id}")
        return

    meta = db.get_job_meta(job_id)
    master_resume_id = meta["master_resume_id"] if meta else None
    if not master_resume_id:
        await update.message.reply_text("⚠️ 找不到 master resume ID")
        return

    confirmed_id = await improver.confirm_resume(
        settings.resume_matcher_url,
        master_resume_id=master_resume_id,
        preview_data=preview_data,
    )
    if not confirmed_id:
        await update.message.reply_text("⚠️ 重試失敗，請稍後再試")
        return

    now = datetime.now(timezone.utc).isoformat()
    db.confirm_job(job_id, confirmed_id, now)
    pdf_url = f"{settings.resume_matcher_url}/api/v1/resumes/{confirmed_id}/pdf"
    await update.message.reply_text(f"✅ 重試成功\n📥 {pdf_url}")


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sc = cfg.get_search_config()
    kw_text = _esc(", ".join(sc.keywords))
    loc_text = _esc(sc.location)
    max_text = str(sc.max_jobs_per_run)
    text = (
        "⚙️ 目前搜尋設定\n\n"
        f"🔍 關鍵字：{kw_text}\n"
        f"📍 地點：{loc_text}\n"
        f"📊 最多職缺數：{max_text}\n\n"
        "修改指令：\n"
        "  `/set_keywords` AI Engineer, ML Engineer\n"
        "  `/set_location` Berlin, Germany\n"
        "  `/set_max` 15"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def cmd_set_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法：/set_keywords AI Engineer, ML Engineer")
        return

    raw = " ".join(context.args)
    keywords = [k.strip() for k in raw.split(",") if k.strip()]
    if not keywords:
        await update.message.reply_text("⚠️ 請提供至少一個關鍵字")
        return

    cfg.set_keywords(keywords)
    await update.message.reply_text(f"✅ 關鍵字已更新：{', '.join(keywords)}")


async def cmd_set_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法：/set_location Berlin, Germany")
        return

    location = " ".join(context.args)
    cfg.set_location(location)
    await update.message.reply_text(f"✅ 地點已更新：{location}")


async def cmd_set_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("用法：/set_max 15")
        return

    n = int(context.args[0])
    cfg.set_max_jobs(n)
    await update.message.reply_text(f"✅ 最多職缺數已更新：{n}")


async def cmd_set_experience_level(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text(
            "用法：/set_experience_level MID_SENIOR_LEVEL, ENTRY_LEVEL"
        )
        return

    raw = " ".join(context.args)
    levels = [lv.strip() for lv in raw.split(",") if lv.strip()]
    if not levels:
        await update.message.reply_text("⚠️ 請提供至少一個經驗等級")
        return

    cfg.set_experience_level(levels)
    await update.message.reply_text(f"✅ 經驗等級已更新：{', '.join(levels)}")


async def cmd_set_blacklist(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not context.args:
        await update.message.reply_text(
            "用法：/set_blacklist EvilCorp, BadInc\n（清空：/set_blacklist -clear）"
        )
        return

    raw = " ".join(context.args)
    if raw.strip() == "-clear":
        cfg.set_blacklist_companies([])
        await update.message.reply_text("✅ 排除名單已清空")
        return

    companies = [c.strip() for c in raw.split(",") if c.strip()]
    cfg.set_blacklist_companies(companies)
    await update.message.reply_text(f"✅ 排除公司已更新：{', '.join(companies)}")


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List jobs waiting for confirm/skip."""
    jobs = db.get_pending_jobs(limit=10)
    if not jobs:
        await update.message.reply_text("目前沒有待決定的職缺 👍")
        return

    lines = [f"⏳ 待決定職缺（{len(jobs)} 筆）：\n"]
    for j in jobs:
        notified = j["notified_at"][:10] if j.get("notified_at") else "—"
        lines.append(f"• {j['title']} @ {j['company']}  ({notified})\n  ID: {j['job_id']}")

    await update.message.reply_text("\n".join(lines))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Available Commands*\n\n"
        "/run \\- Manually trigger the job search pipeline\n"
        "/status \\- Show today's job statistics\n"
        "/pending \\- List jobs waiting for confirm/skip\n"
        "/list \\- List recently confirmed jobs with PDF links\n"
        "/retry `<job_id>` \\- Retry confirming a resume for a job\n"
        "/config \\- Show basic search configuration\n"
        "/search\\_config \\- Show full config incl\\. experience level & blacklist\n"
        "/set\\_keywords `<kw1, kw2>` \\- Update search keywords\n"
        "/set\\_location `<location>` \\- Update search location\n"
        "/set\\_max `<n>` \\- Set max jobs per run\n"
        "/set\\_experience\\_level `<level1, level2>` \\- Update experience filter\n"
        "/set\\_blacklist `<co1, co2>` \\- Update company blacklist\n"
        "/help \\- Show this help message"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def cmd_search_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show full search config including experience_level and blacklist_companies."""
    sc = cfg.get_search_config()
    exp_text = _esc(", ".join(sc.experience_level) if sc.experience_level else "—")
    blacklist_text = _esc(", ".join(sc.blacklist_companies) if sc.blacklist_companies else "—")
    kw_text = _esc(", ".join(sc.keywords))
    loc_text = _esc(sc.location)

    text = (
        "⚙️ *完整搜尋設定*\n\n"
        f"🔍 關鍵字：{kw_text}\n"
        f"📍 地點：{loc_text}\n"
        f"📊 最多職缺數：{sc.max_jobs_per_run}\n"
        f"🎯 經驗等級：{exp_text}\n"
        f"🚫 排除公司：{blacklist_text}"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ── util ───────────────────────────────────────────────────────────────────


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    # Escape backslash first to avoid double-escaping
    text = text.replace("\\", "\\\\")
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _esc_url(url: str) -> str:
    """Escape URL for use inside MarkdownV2 inline link parentheses.

    Only ) and \\ need escaping inside the URL part of [text](url).
    """
    return url.replace("\\", "\\\\").replace(")", "\\)")
