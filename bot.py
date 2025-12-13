import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from mongo import groups
from start import start_cmd
from text_nsfw import is_nsfw_text

BOT_TOKEN = os.getenv("BOT_TOKEN")


# -------- ADMIN CHECK --------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ("administrator", "creator")


# -------- /nsfw enable --------
async def nsfw_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": True}},
        upsert=True
    )
    await update.message.reply_text("✅ NSFW filter enabled")


# -------- /nsfw disable --------
async def nsfw_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    groups.update_one(
        {"chat_id": update.effective_chat.id},
        {"$set": {"enabled": False}},
        upsert=True
    )
    await update.message.reply_text("❌ NSFW filter disabled")


# -------- /stats --------
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = groups.count_documents({"enabled": True})
    disabled = groups.count_documents({"enabled": False})

    await update.message.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"✅ Enabled groups: {enabled}\n"
        f"❌ Disabled groups: {disabled}",
        parse_mode="Markdown"
    )


# -------- TEXT HANDLER --------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return

    cfg = groups.find_one({"chat_id": update.effective_chat.id})
    if not cfg or not cfg.get("enabled"):
        return

    if await is_admin(update, context):
        return

    text = update.message.text
    if not text:
        return

    if is_nsfw_text(text):
        await update.message.delete()


# -------- MAIN --------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("nsfw", nsfw_enable, filters.Regex("^/nsfw enable")))
    app.add_handler(CommandHandler("nsfw", nsfw_disable, filters.Regex("^/nsfw disable")))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Simple NSFW Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()