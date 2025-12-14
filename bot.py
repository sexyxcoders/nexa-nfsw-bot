import os
import cv2
import requests
import tempfile
from datetime import datetime
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

groups = db.groups     # group settings
clones = db.clones     # cloned bot tokens

print("✅ MongoDB connected")

# ================= HELPERS =================
async def is_admin(chat_id: int, user_id: int, context):
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False


async def get_admin_mentions(context, chat_id):
    admins = await context.bot.get_chat_administrators(chat_id)
    mentions = []
    for a in admins:
        if a.user.username:
            mentions.append(f"@{a.user.username}")
    return " ".join(mentions) if mentions else "👮 Admins"


def format_log(data: dict) -> str:
    scores = data.get("scores", {})
    return (
        "📊 *Confidence Scores:*\n"
        f"😐 Neutral    : {scores.get('neutral',0)*100:.2f}%\n"
        f"🎨 Drawings   : {scores.get('drawings',0)*100:.2f}%\n"
        f"💋 Sexy       : {scores.get('sexy',0)*100:.2f}%\n"
        f"🔞 Porn       : {scores.get('porn',0)*100:.2f}%\n"
        f"👾 Hentai     : {scores.get('hentai',0)*100:.2f}%"
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
        "🛡 **Nexa NSFW Moderation Bot**\n\n"
        "👮 Admin:\n"
        "/nsfw enable | disable\n"
        "/stats\n\n"
        "🧬 Public:\n"
        "/clone – clone this bot\n"
        "/revoke – revoke clone\n\n"
        "⚠️ Bot must have *Delete Messages* permission",
        parse_mode="Markdown"
    )


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return

    if not await is_admin(chat.id, user.id, context):
        return await update.message.reply_text("❌ Admins only")

    if not context.args:
        return await update.message.reply_text("/nsfw enable | disable")

    enabled = context.args[0].lower() == "enable"

    groups.update_one(
        {"chat_id": chat.id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )

    await update.message.reply_text(
        "✅ NSFW filter enabled" if enabled else "❌ NSFW filter disabled"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    e = groups.count_documents({"enabled": True})
    d = groups.count_documents({"enabled": False})
    c = clones.count_documents({})

    await update.message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"Enabled Groups: {e}\n"
        f"Disabled Groups: {d}\n"
        f"Cloned Bots: {c}",
        parse_mode="Markdown"
    )


# ================= CLONE SYSTEM =================
async def clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_clone_token"] = True
    await update.message.reply_text(
        "🧬 **Clone Nexa NSFW Bot**\n\n"
        "1️⃣ Create a bot via @BotFather\n"
        "2️⃣ Send the *BOT TOKEN* here\n\n"
        "⚠️ Send only the token",
        parse_mode="Markdown"
    )


async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = clones.delete_one({"owner_id": update.effective_user.id})
    if res.deleted_count:
        await update.message.reply_text("🗑️ Clone revoked successfully")
    else:
        await update.message.reply_text("ℹ️ No active clone found")

# ================= WATCHER =================
async def watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.from_user if msg else None

    if not msg:
        return

    # ---- CLONE TOKEN INPUT ----
    if context.user_data.get("awaiting_clone_token") and msg.text:
        token = msg.text.strip()

        if ":" not in token:
            return await msg.reply_text("❌ Invalid BOT TOKEN")

        clones.update_one(
            {"owner_id": user.id},
            {"$set": {
                "bot_token": token,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )

        context.user_data["awaiting_clone_token"] = False
        return await msg.reply_text(
            "✅ Clone saved!\n\n"
            "🚀 Deploy it on Heroku using your own repo."
        )

    # ---- GROUP ONLY ----
    if chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": chat.id})
    if not cfg or not cfg.get("enabled"):
        return

    async def safe_delete():
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except Exception as e:
            print("DELETE FAILED:", e)

    username = f"@{user.username}" if user.username else user.first_name
    admins = await get_admin_mentions(context, chat.id)

    # ===== VIDEO / GIF =====
    if msg.video or msg.animation:
        file = await (msg.video or msg.animation).get_file()
        path = f"/tmp/{file.file_unique_id}.mp4"
        await file.download_to_drive(path)

        is_nsfw, data = scan_video(path)
        if is_nsfw:
            await safe_delete()
            await context.bot.send_message(
                chat.id,
                f"{admins}\n\n"
                f"🎥 *NSFW VIDEO DELETED*\n"
                f"👤 User: {username}\n\n"
                f"{format_log(data)}",
                parse_mode="Markdown"
            )
        return

    # ===== TEXT =====
    if msg.text or msg.caption:
        is_nsfw, _ = scan_text(msg.text or msg.caption)
        if is_nsfw:
            await safe_delete()
            await context.bot.send_message(
                chat.id,
                f"{admins}\n\n"
                f"📝 *NSFW TEXT DELETED*\n"
                f"👤 User: {username}",
                parse_mode="Markdown"
            )
            return

    # ===== IMAGE =====
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)

        is_nsfw, data = scan_image(path)
        if is_nsfw:
            await safe_delete()
            await context.bot.send_message(
                chat.id,
                f"{admins}\n\n"
                f"🖼 *NSFW IMAGE DELETED*\n"
                f"👤 User: {username}\n\n"
                f"{format_log(data)}",
                parse_mode="Markdown"
            )

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("nsfw", nsfw))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("clone", clone))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(MessageHandler(filters.ALL, watcher))

    print("🤖 Nexa NSFW Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()