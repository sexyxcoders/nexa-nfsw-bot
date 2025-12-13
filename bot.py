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
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        m = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id
        )
        return m.status in ("administrator", "creator")
    except:
        return False


def scan_text(text: str) -> bool:
    try:
        r = requests.post(
            NSFW_API,
            json={"text": text},
            timeout=10
        )
        print("TEXT API:", r.text)
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
        print("IMAGE API:", r.text)
        return r.json().get("nsfw", False)
    except Exception as e:
        print("IMAGE API ERROR:", e)
        return False


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡 Nexa NSFW Detector Bot\n\n"
        "Admin commands:\n"
        "/nsfw enable\n"
        "/nsfw disable\n"
        "/stats\n\n"
        "⚠️ Bot must be admin with delete permission."
    )


async def nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return

    if not await is_admin(update, context):
        return await update.message.reply_text("❌ Admins only")

    if not context.args:
        return await update.message.reply_text("/nsfw enable | disable")

    enabled = context.args[0].lower() == "enable"

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )

    await update.message.reply_text(
        "✅ NSFW filter enabled" if enabled else "❌ NSFW filter disabled"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    e = groups.count_documents({"enabled": True})
    d = groups.count_documents({"enabled": False})

    await update.message.reply_text(
        f"📊 Bot Stats\n\n"
        f"Enabled groups: {e}\n"
        f"Disabled groups: {d}"
    )


# ================= MESSAGE WATCHER =================
async def watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": update.effective_chat.id})
    print("CFG:", cfg)

    if not cfg or not cfg.get("enabled"):
        return

    # 🚫 Block GIF / Video / Sticker instantly
    if msg.animation or msg.video or msg.sticker:
        await msg.delete()
        print("MEDIA DELETED")
        return

    # 📝 Text
    if msg.text or msg.caption:
        if scan_text(msg.text or msg.caption):
            await msg.delete()
            print("TEXT DELETED")
            return

    # 🖼 Image
    if msg.photo:
        file = await msg.photo[-1].get_file()
        path = f"/tmp/{file.file_unique_id}.jpg"
        await file.download_to_drive(path)

        if scan_image(path):
            await msg.delete()
            print("IMAGE DELETED")


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