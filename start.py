from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes

# ================= CONFIG =================
BOT_NAME = "Nexa NSFW Guard"

OWNER_USERNAME = "YourUsername"        # without @
SUPPORT_CHAT = "YourSupportGroup"      # without @
SUPPORT_CHANNEL = "YourChannel"        # without @

# Public image URL (Telegram accepts only https)
START_IMAGE = "https://i.imgur.com/8Km9tLL.jpg"
# =========================================


START_TEXT = (
    "👋 **Welcome {name}!**\n\n"
    "🤖 **{bot}** is an advanced AI-powered NSFW moderation bot.\n\n"
    "✨ **Features:**\n"
    "• 🖼 Image NSFW Detection\n"
    "• 🧠 AI Text NSFW Detection\n"
    "• 🚫 Bad Words & Link Protection\n"
    "• ⚠️ Warning System\n"
    "• 🔇 3 Warnings → Auto Mute\n\n"
    "🧑‍💼 **Admin Commands:**\n"
    "`/nsfw enable` – Enable moderation\n"
    "`/nsfw disable` – Disable moderation\n\n"
    "📌 Add me to a group and make me **admin** to work properly."
)

HELP_TEXT = (
    "📖 **Help Menu**\n\n"
    "🔹 **Commands:**\n"
    "`/start` – Start bot\n"
    "`/help` – Show help\n"
    "`/ping` – Check bot status\n"
    "`/stats` – Bot statistics\n"
    "`/nsfw enable` – Enable NSFW moderation\n"
    "`/nsfw disable` – Disable NSFW moderation\n\n"
    "🔹 **Moderation:**\n"
    "• NSFW images → auto delete\n"
    "• NSFW / abusive text → auto delete\n"
    "• Links & bio promotion → blocked\n"
    "• 3 warnings → auto mute\n\n"
    "💬 Need help? Use the buttons below."
)


def start_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛡 Enable NSFW", callback_data="enable_info"),
                InlineKeyboardButton("❌ Disable NSFW", callback_data="disable_info")
            ],
            [
                InlineKeyboardButton("📖 Help", callback_data="help")
            ],
            [
                InlineKeyboardButton(
                    "💬 Support Chat",
                    url=f"https://t.me/{SUPPORT_CHAT}"
                ),
                InlineKeyboardButton(
                    "📢 Support Channel",
                    url=f"https://t.me/{SUPPORT_CHANNEL}"
                )
            ],
            [
                InlineKeyboardButton(
                    "👑 Owner",
                    url=f"https://t.me/{OWNER_USERNAME}"
                )
            ]
        ]
    )


# ---------------- /start ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    text = START_TEXT.format(
        name=user.first_name,
        bot=BOT_NAME
    )

    # Private chat → image + buttons
    if chat.type == "private":
        await context.bot.send_photo(
            chat_id=chat.id,
            photo=START_IMAGE,
            caption=text,
            parse_mode="Markdown",
            reply_markup=start_buttons()
        )
    else:
        # Group chat → short intro
        await update.message.reply_text(
            f"👋 I'm **{BOT_NAME}**\n"
            f"Use `/nsfw enable` to activate moderation.",
            parse_mode="Markdown"
        )


# ---------------- /help ----------------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=start_buttons()
    )


# ---------------- Button Callbacks ----------------
async def start_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.edit_message_caption(
            caption=HELP_TEXT,
            parse_mode="Markdown",
            reply_markup=start_buttons()
        )

    elif query.data == "enable_info":
        await query.answer(
            "Use /nsfw enable in a group (admin only)",
            show_alert=True
        )

    elif query.data == "disable_info":
        await query.answer(
            "Use /nsfw disable in a group (admin only)",
            show_alert=True
        )
