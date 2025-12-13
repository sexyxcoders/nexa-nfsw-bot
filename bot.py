import os
import requests
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
async def is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False


def scan_text(text: str) -> bool:
    try:
        r = requests.post(
            NSFW_API,
            json={"text": text},
            timeout=10
        )
        print("🧠 TEXT API:", r.text)
        return r.json().get("nsfw", False)
    except Exception as e:
        print("TEXT API ERROR:", e)
        return False


def scan_image(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            r = requests.post(
                NSFW_API,
                files={"file": ("image.jpg", f, "image/jpeg")},
                timeout=15
            )
        print("🖼 IMAGE API:", r.text)
        return r.json().get("nsfw", False)
    except Exception as e:
        print("IMAGE API ERROR:", e)
        return False


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🛡 **Nexa NSFW Detector Bot**\n\n"
        "Admin commands:\n"
        "/nsfw enable\n"
        "/nsfw disable\n"
        "/stats\n\n"
        "⚠️ Bot must be admin with *Delete Messages* permission.",
        parse_mode="Markdown"
    )


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        return

    if not await is_admin(chat.id, update.effective_user.id, context):
        return await update.effective_message.reply_text("❌ Admins only")

    if not context.args:
        return await update.effective_message.reply_text("/nsfw enable | disable")

    enabled = context.args[0].lower() == "enable"

    groups.update_one(
        {"chat_id": chat.id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )

    await update.effective_message.reply_text(
        "✅ NSFW filter enabled" if enabled else "❌ NSFW filter disabled"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    e = groups.count_documents({"enabled": True})
    d = groups.count_documents({"enabled": False})

    await update.effective_message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"✅ Enabled groups: {e}\n"
        f"❌ Disabled groups: {d}",
        parse_mode="Markdown"
    )


# ================= MESSAGE WATCHER =================
async def watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if not msg or chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": chat.id})
    print("CFG:", cfg)

    if not cfg or not cfg.get("enabled"):
        return

    async def safe_delete():
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
            print("❌ MESSAGE DELETED")
        except Exception as e:
            print("🚫 DELETE FAILED:", e)

    # 🚫 BLOCK MEDIA (GIF / VIDEO / STICKER)
    if msg.animation or msg.video or msg.sticker:
        await safe_delete()
        return

    # 📝 TEXT
    if msg.text or msg.caption:
        if scan_text(msg.text or msg.caption):
            await safe_delete()
            return

    # 🖼 IMAGE
    if msg.photo:
        try:
            file = await msg.photo[-1].get_file()
            path = f"/tmp/{file.file_unique_id}.jpg"
            await file.download_to_drive(path)

            if scan_image(path):
                await safe_delete()
        except Exception as e:
            print("IMAGE ERROR:", e)


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