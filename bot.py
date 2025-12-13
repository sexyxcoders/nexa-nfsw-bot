import os
import time
import requests

from telegram import (
    Update,
    ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from mongo import groups, users
from start import start_cmd, help_cmd, start_callbacks
from text_ai import is_nsfw_text
from filters_text import contains_bad_words, contains_links_or_bio


# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://NexaCoders-nexa-api.hf.space/scan"

MAX_WARNINGS = 3
MUTE_TIME = 300  # seconds (5 minutes)
# =========================================


# ---------------- ADMIN CHECK ----------------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ("administrator", "creator")


# ---------------- BASIC COMMANDS ----------------
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is running.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_count = groups.count_documents({})
    user_count = users.count_documents({})

    await update.message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"👥 Groups: {group_count}\n"
        f"🙋 Users tracked: {user_count}",
        parse_mode="Markdown"
    )


# ---------------- NSFW ENABLE / DISABLE ----------------
async def nsfw_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Admin only command")
        return

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": True}},
        upsert=True
    )

    await update.message.reply_text("✅ NSFW moderation ENABLED for this group")


async def nsfw_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("❌ Admin only command")
        return

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": False}},
        upsert=True
    )

    await update.message.reply_text("❌ NSFW moderation DISABLED for this group")


# ---------------- WARNING SYSTEM ----------------
async def add_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    record = users.find_one(
        {"chat_id": chat_id, "user_id": user_id}
    ) or {"count": 0}

    count = record["count"] + 1

    users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"count": count}},
        upsert=True
    )

    if count >= MAX_WARNINGS:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(time.time()) + MUTE_TIME
        )
        users.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"count": 0}}
        )
        await update.effective_chat.send_message(
            "🔇 User muted (3 NSFW violations)"
        )
    else:
        await update.effective_chat.send_message(
            f"⚠️ NSFW Warning {count}/{MAX_WARNINGS}"
        )


# ---------------- IMAGE HANDLER ----------------
async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    cfg = groups.find_one({"chat_id": chat_id})
    if not cfg or not cfg.get("enabled"):
        return

    member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if member.status in ("administrator", "creator"):
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()

    try:
        res = requests.post(
            API_URL,
            files={"file": ("image.jpg", img_bytes)},
            timeout=60
        )
        data = res.json()
    except Exception:
        return

    if data.get("primary") in ("porn", "hentai", "sexy"):
        await update.message.delete()
        await add_warning(update, context)


# ---------------- TEXT HANDLER ----------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if not text:
        return

    cfg = groups.find_one({"chat_id": chat_id})
    if not cfg or not cfg.get("enabled"):
        return

    member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if member.status in ("administrator", "creator"):
        return

    violation = (
        contains_links_or_bio(text)
        or contains_bad_words(text)
        or is_nsfw_text(text)
    )

    if violation:
        await update.message.delete()
        await add_warning(update, context)


# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Start & Help
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(start_callbacks))

    # Core commands
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("nsfw", nsfw_enable, filters.Regex("^/nsfw enable")))
    app.add_handler(CommandHandler("nsfw", nsfw_disable, filters.Regex("^/nsfw disable")))

    # Content handlers
    app.add_handler(MessageHandler(filters.PHOTO, image_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Nexa NSFW Moderation Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
