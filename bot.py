import os
import cv2
import asyncio
import requests
import tempfile
from telegram import Update
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

print("✅ MongoDB connected")

# ================= HELPERS =================
async def is_admin(chat_id: int, user_id: int, context):
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False


async def send_temp_message(context, chat_id, text, delay=20):
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown"
    )
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass


def format_log(data: dict) -> str:
    scores = data.get("scores", {})
    return (
        "> 📊 *Confidence Scores:*\n"
        f"> 😐 Neutral    : {scores.get('neutral',0)*100:.2f}%\n"
        f"> 🎨 Drawings   : {scores.get('drawings',0)*100:.2f}%\n"
        f"> 💋 Sexy       : {scores.get('sexy',0)*100:.2f}%\n"
        f"> 🔞 Porn       : {scores.get('porn',0)*100:.2f}%\n"
        f"> 👾 Hentai     : {scores.get('hentai',0)*100:.2f}%"
    )

# ================= SCANNERS =================
def scan_text(text: str):
    try:
        r = requests.post(NSFW_API, json={"text": text}, timeout=10)
        data = r.json()
        return data.get("safe") is False, data
    except:
        return False, {}


def scan_image(path: str):
    try:
        with open(path, "rb") as f:
            r = requests.post(
                NSFW_API,
                files={"file": ("image.jpg", f, "image/jpeg")},
                timeout=15
            )
        data = r.json()
        return data.get("safe") is False, data
    except:
        return False, {}


def scan_video(path: str):
    cap = cv2.VideoCapture(path)
    frame_no = 0

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame_no += 1
        if frame_no % 15 != 0:
            continue

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, frame)
            try:
                with open(tmp.name, "rb") as f:
                    r = requests.post(
                        NSFW_API,
                        files={"file": ("frame.jpg", f, "image/jpeg")},
                        timeout=15
                    )
                data = r.json()
                if data.get("safe") is False:
                    cap.release()
                    return True, data
            except:
                pass

    cap.release()
    return False, {}

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "> 🛡 *Nexa NSFW Moderation Bot*\n>\n"
        "> Admin Commands:\n"
        "> /nsfw enable\n"
        "> /nsfw disable\n"
        "> /stats\n>\n"
        "> Detects NSFW text, images, stickers, GIFs & videos\n"
        "> Bot must have *Delete Messages* permission",
        parse_mode="Markdown"
    )


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return

    if not await is_admin(chat.id, user.id, context):
        return await update.message.reply_text("> ❌ Admins only", parse_mode="Markdown")

    if not context.args:
        return await update.message.reply_text(
            "> Usage: /nsfw enable | disable", parse_mode="Markdown"
        )

    enabled = context.args[0].lower() == "enable"

    groups.update_one(
        {"chat_id": chat.id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )

    await update.message.reply_text(
        "> ✅ NSFW filter enabled" if enabled else "> ❌ NSFW filter disabled",
        parse_mode="Markdown"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    e = groups.count_documents({"enabled": True})
    d = groups.count_documents({"enabled": False})

    await update.message.reply_text(
        f"> 📊 *Bot Stats*\n>\n"
        f"> Enabled Groups : {e}\n"
        f"> Disabled Groups: {d}",
        parse_mode="Markdown"
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

    async def safe_delete():
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except:
            pass

    username = f"@{user.username}" if user.username else user.first_name

    # 🎥 VIDEO / GIF
    if msg.video or msg.animation:
        file = await (msg.video or msg.animation).get_file()
        path = f"/tmp/{file.file_unique_id}.mp4"
        await file.download_to_drive(path)

        nsfw, data = scan_video(path)
        if nsfw:
            await safe_delete()
            await send_temp_message(
                context,
                chat.id,
                f"> 🎥 *NSFW VIDEO DELETED*\n"
                f"> User: {username}\n>\n"
                f"{format_log(data)}"
            )
        return

    # 🧩 STICKER
    if msg.sticker:
        file = await msg.sticker.get_file()
        path = f"/tmp/{file.file_unique_id}.png"
        await file.download_to_drive(path)

        nsfw, data = scan_image(path)
        if nsfw:
            await safe_delete()
            await send_temp_message(
                context,
                chat.id,
                f"> 🧩 *NSFW STICKER DELETED*\n"
                f"> User: {username}\n>\n"
                f"{format_log(data)}"
            )
        return

    # 🖼 IMAGE
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)

        nsfw, data = scan_image(path)
        if nsfw:
            await safe_delete()
            await send_temp_message(
                context,
                chat.id,
                f"> 🖼 *NSFW IMAGE DELETED*\n"
                f"> User: {username}\n>\n"
                f"{format_log(data)}"
            )
        return

    # 📝 TEXT
    if msg.text or msg.caption:
        nsfw, _ = scan_text(msg.text or msg.caption)
        if nsfw:
            await safe_delete()
            await send_temp_message(
                context,
                chat.id,
                f"> 📝 *NSFW TEXT DELETED*\n"
                f"> User: {username}"
            )

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