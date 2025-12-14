import os
import cv2
import asyncio
import tempfile
import requests
from datetime import datetime
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from pymongo import MongoClient

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
NSFW_API = "https://NexaCoders-nexa-api.hf.space/scan"

# ================= DATABASE =================
mongo = MongoClient(MONGO_URL)
db = mongo["nexa_nsfw"]
groups = db.groups
warnings = db.warnings

print("✅ MongoDB connected")

# ================= HELPERS =================
async def is_admin(chat_id, user_id, context):
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False


async def send_temp(context, chat_id, text, reply_to=None):
    msg = await context.bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_to_message_id=reply_to
    )
    await asyncio.sleep(20)
    try:
        await msg.delete()
    except:
        pass


async def add_warning(context, chat, user):
    rec = warnings.find_one({"chat_id": chat.id, "user_id": user.id})
    count = rec["count"] + 1 if rec else 1

    warnings.update_one(
        {"chat_id": chat.id, "user_id": user.id},
        {"$set": {"count": count}},
        upsert=True
    )

    if count < 3:
        await send_temp(
            context,
            chat.id,
            f"> ⚠️ *NSFW Warning {count}/3*\n> User: {user.first_name}"
        )
    else:
        try:
            await context.bot.restrict_chat_member(
                chat.id,
                user.id,
                ChatPermissions(can_send_messages=False),
                until_date=int(datetime.utcnow().timestamp()) + 600
            )
        except:
            pass

        warnings.delete_one({"chat_id": chat.id, "user_id": user.id})

        await send_temp(
            context,
            chat.id,
            f"> 🔇 *User Muted (10 min)*\n> Reason: NSFW (3 strikes)\n> User: {user.first_name}"
        )


def scan_text(text):
    try:
        r = requests.post(NSFW_API, json={"text": text}, timeout=10)
        data = r.json()
        return data.get("safe") is False
    except:
        return False


def scan_image(path):
    try:
        with open(path, "rb") as f:
            r = requests.post(
                NSFW_API,
                files={"file": ("img.jpg", f, "image/jpeg")},
                timeout=15
            )
        return r.json().get("safe") is False
    except:
        return False


def scan_video(path):
    cap = cv2.VideoCapture(path)
    i = 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if i % 15 != 0:
            continue
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, frame)
            if scan_image(tmp.name):
                cap.release()
                return True
    cap.release()
    return False


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡 *Nexa NSFW Moderation Bot*\n\n"
        "> Detects NSFW text, images, GIFs, videos & stickers\n"
        "> 3 warnings → auto mute\n\n"
        "Admin:\n/nsfw enable | disable\n/stats",
        parse_mode="Markdown"
    )


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not await is_admin(chat.id, update.effective_user.id, context):
        return

    if not context.args:
        return await update.message.reply_text("/nsfw enable | disable")

    enabled = context.args[0].lower() == "enable"
    groups.update_one(
        {"chat_id": chat.id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )
    await update.message.reply_text(
        "✅ Enabled" if enabled else "❌ Disabled"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"> Enabled Groups: {groups.count_documents({'enabled': True})}\n"
        f"> Active Warnings: {warnings.count_documents({})}"
    )


# ================= WATCHER =================
async def watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.from_user if msg else None

    if not msg or chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": chat.id})
    if not cfg or not cfg.get("enabled"):
        return

    async def delete():
        try:
            await msg.delete()
        except:
            pass

    # TEXT
    if msg.text or msg.caption:
        if scan_text(msg.text or msg.caption):
            await delete()
            await add_warning(context, chat, user)
            return

    # IMAGE
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)
        if scan_image(path):
            await delete()
            await add_warning(context, chat, user)
            return

    # VIDEO / GIF
    if msg.video or msg.animation:
        file = await (msg.video or msg.animation).get_file()
        path = f"/tmp/{file.file_unique_id}.mp4"
        await file.download_to_drive(path)
        if scan_video(path):
            await delete()
            await add_warning(context, chat, user)
            return

    # STICKER
    if msg.sticker:
        file = await msg.sticker.get_file()
        path = f"/tmp/{file.file_unique_id}.png"
        await file.download_to_drive(path)
        if scan_image(path):
            await delete()
            await add_warning(context, chat, user)


# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nsfw", nsfw))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.ALL, watcher))

    print("🤖 Nexa NSFW Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()