"""Telegram Bot: notifications + inline confirm/skip + search config commands."""
from __future__ import annotations

import asyncio
import json
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
    app.add_handler(CommandHandler("search_config", cmd_search_config))
    app.add_handler(CommandHandler("set_keywords", cmd_set_keywords))
    app.add_handler(CommandHandler("set_location", cmd_set_location))
    app.add_handler(CommandHandler("set_max", cmd_set_max))
    app.add_handler(CommandHandler("help", cmd_help))
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
    """Send a MarkdownV2 run-complete summary if any jobs were found."""
    if found == 0:
        return
    text = (
        f"✅ Run complete: {_esc(str(found))} new jobs found, "
        f"{_esc(str(tailored))} tailored, "
        f"{_esc(str(failed))} failed"
    )
    await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2")


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
    payload_json = db.get_confirm_payload(job_id)
    if not payload_json:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ 找不到 confirm payload，請用 /retry " + job_id)
        return

    confirmed_id = await improver.confirm_resume(settings.resume_matcher_url, json.loads(payload_json))
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
    preview_id = db.get_preview_resume_id(job_id)
    if preview_id:
        await improver.delete_preview(settings.resume_matcher_url, preview_id)

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
    payload_json = db.get_confirm_payload(job_id)
    if not payload_json:
        await update.message.reply_text(f"找不到 job_id: {job_id}")
        return

    confirmed_id = await improver.confirm_resume(settings.resume_matcher_url, json.loads(payload_json))
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


async def cmd_search_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sc = cfg.get_search_config()
    kw_text = _esc(", ".join(sc.keywords))
    loc_text = _esc(sc.location)
    max_text = str(sc.max_jobs_per_run)
    exp_text = _esc(", ".join(sc.experience_level))
    bl_text = _esc(", ".join(sc.blacklist_companies) if sc.blacklist_companies else "—")
    text = (
        "⚙️ 完整搜尋設定\n\n"
        f"🔍 關鍵字：{kw_text}\n"
        f"📍 地點：{loc_text}\n"
        f"📊 最多職缺數：{max_text}\n"
        f"🎓 經驗等級：{exp_text}\n"
        f"🚫 排除公司：{bl_text}"
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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *Available Commands*\n\n"
        "/run \\- Manually trigger the job search pipeline\n"
        "/status \\- Show today's job statistics\n"
        "/list \\- List recently confirmed jobs with PDF links\n"
        "/retry `<job_id>` \\- Retry confirming a resume for a job\n"
        "/config \\- Show current search configuration\n"
        "/search\\_config \\- Show full config incl\\. experience level \\& blacklist\n"
        "/set\\_keywords `<kw1, kw2>` \\- Update search keywords\n"
        "/set\\_location `<location>` \\- Update search location\n"
        "/set\\_max `<n>` \\- Set max jobs per run\n"
        "/help \\- Show this help message"
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
