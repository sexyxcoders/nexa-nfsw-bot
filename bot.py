import os
import requests
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

groups = db.groups       # group settings
clones = db.clones       # cloned bots

print("✅ MongoDB connected")

# ================= HELPERS =================
async def is_admin(chat_id: int, user_id: int, context):
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False


async def alert_admins(context, chat_id, text):
    admins = await context.bot.get_chat_administrators(chat_id)
    for admin in admins:
        try:
            await context.bot.send_message(admin.user.id, text)
        except:
            pass


def scan_text(text: str) -> bool:
    try:
        r = requests.post(NSFW_API, json={"text": text}, timeout=10)
        data = r.json()
        return data.get("safe") is False
    except:
        return False


def scan_image(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            r = requests.post(
                NSFW_API,
                files={"file": ("image.jpg", f, "image/jpeg")},
                timeout=15
            )
        data = r.json()
        return data.get("safe") is False
    except:
        return False


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡 **Nexa NSFW Moderation Bot**\n\n"
        "👮 Admin:\n"
        "/nsfw enable | disable\n"
        "/stats\n\n"
        "🧬 Public:\n"
        "/clone – clone bot\n"
        "/revoke – revoke clone\n\n"
        "⚠️ Bot must have DELETE permission.",
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
        f"Groups Enabled: {e}\n"
        f"Groups Disabled: {d}\n"
        f"Cloned Bots: {c}",
        parse_mode="Markdown"
    )


# ================= CLONE =================
async def clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧬 **Clone Nexa NSFW Bot**\n\n"
        "1️⃣ Create bot via @BotFather\n"
        "2️⃣ Send BOT TOKEN here\n\n"
        "⚠️ Send only token",
        parse_mode="Markdown"
    )
    context.user_data["awaiting_token"] = True


async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = clones.delete_one({"owner_id": update.effective_user.id})

    if res.deleted_count:
        await update.message.reply_text("🗑️ Clone revoked successfully")
    else:
        await update.message.reply_text("ℹ️ No clone found")


# ================= WATCHER =================
async def watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = msg.from_user if msg else None

    if not msg:
        return

    # ---- CLONE TOKEN INPUT ----
    if context.user_data.get("awaiting_token") and msg.text:
        token = msg.text.strip()

        if ":" not in token:
            return await msg.reply_text("❌ Invalid BOT TOKEN")

        clones.update_one(
            {"owner_id": user.id},
            {"$set": {
                "bot_token": token,
                "created": datetime.utcnow()
            }},
            upsert=True
        )

        context.user_data["awaiting_token"] = False

        return await msg.reply_text(
            "✅ Token saved!\n\n"
            "🚀 Deploy:\n"
            "https://heroku.com/deploy"
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

    # 🎥 VIDEO / GIF / STICKER → ALERT
    if msg.video or msg.animation or msg.sticker:
        await alert_admins(
            context,
            chat.id,
            f"⚠️ Media detected\n"
            f"User: {username}\n"
            f"ID: {user.id}\n"
            f"Group: {chat.title}"
        )
        return

    # 📝 TEXT
    if msg.text or msg.caption:
        if scan_text(msg.text or msg.caption):
            await safe_delete()
            await alert_admins(
                context,
                chat.id,
                f"🚨 NSFW TEXT DELETED\n"
                f"User: {username}\n"
                f"Group: {chat.title}"
            )
            return

    # 🖼 IMAGE
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)

        if scan_image(path):
            await safe_delete()
            await alert_admins(
                context,
                chat.id,
                f"🚨 NSFW IMAGE DELETED\n"
                f"User: {username}\n"
                f"Group: {chat.title}"
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