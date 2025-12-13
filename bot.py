import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from pymongo import MongoClient

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# ================== DATABASE ==================
client = MongoClient(MONGO_URL)
db = client["nsfw_bot"]
groups = db["groups"]

print("✅ MongoDB connected")

# ================== HELPERS ==================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, user_id
        )
        return member.status in ("administrator", "creator")
    except:
        return False


# ================== COMMANDS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🛡 **NSFW Detector Bot**\n\n"
        "Commands (admins only):\n"
        "/nsfw enable\n"
        "/nsfw disable\n"
        "/stats\n\n"
        "Make me admin with delete permission.",
        parse_mode="Markdown"
    )


async def nsfw_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return

    if not await is_admin(update, context, update.effective_user.id):
        await update.effective_message.reply_text("❌ Admins only")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Usage:\n/nsfw enable\n/nsfw disable"
        )
        return

    action = context.args[0].lower()

    if action == "enable":
        groups.update_one(
            {"chat_id": update.effective_chat.id},
            {"$set": {"enabled": True}},
            upsert=True
        )
        await update.effective_message.reply_text("✅ NSFW filter enabled")

    elif action == "disable":
        groups.update_one(
            {"chat_id": update.effective_chat.id},
            {"$set": {"enabled": False}},
            upsert=True
        )
        await update.effective_message.reply_text("❌ NSFW filter disabled")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = groups.count_documents({"enabled": True})
    disabled = groups.count_documents({"enabled": False})

    await update.effective_message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"✅ Enabled groups: {enabled}\n"
        f"❌ Disabled groups: {disabled}",
        parse_mode="Markdown"
    )

# ================== NSFW DETECTOR ==================
NSFW_WORDS = [
    "sex", "porn", "xxx", "nude", "boobs",
    "fuck", "hentai", "slut", "bitch"
]

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    if update.effective_chat.type == "private":
        return

    # Check if enabled
    cfg = groups.find_one({"chat_id": update.effective_chat.id})
    if not cfg or not cfg.get("enabled"):
        return

    # Ignore admin messages
    if await is_admin(update, context, msg.from_user.id):
        return

    text = msg.text or msg.caption
    if not text:
        return

    text_lower = text.lower()
    print("🔎 CHECKING:", text_lower)

    for word in NSFW_WORDS:
        if word in text_lower:
            try:
                await msg.delete()
                print("❌ NSFW MESSAGE DELETED")
            except Exception as e:
                print("🚫 DELETE ERROR:", e)
            break


# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("nsfw", nsfw_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))

    # IMPORTANT: filters.ALL + effective_message
    app.add_handler(MessageHandler(filters.ALL, text_handler))

    print("🤖 NSFW Bot is running")
    app.run_polling()


if __name__ == "__main__":
    main()