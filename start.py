from pyrogram import Client, filters
from pyrogram.types import Message


# =====================================================
# /start → PRIVATE CHAT
# =====================================================
@Client.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message):
    text = (
        "🤖 **Nexa NSFW Protection Bot**\n\n"
        "🛡 AI-powered content moderation for Telegram groups\n\n"
        "🔍 **What I can do:**\n"
        "• Detect NSFW images\n"
        "• Detect NSFW stickers & GIFs\n"
        "• Real-time AI analysis\n"
        "• Auto delete unsafe content\n"
        "• Temporary logs (auto-delete)\n\n"
        "⚙️ **How to use me:**\n"
        "1️⃣ Add me to your group\n"
        "2️⃣ Make me **Admin**\n"
        "3️⃣ Give **Delete Messages** permission\n"
        "4️⃣ Use `/nsfw on` in the group\n\n"
        "👮 **Admin Commands (Group):**\n"
        "• `/nsfw on` – Enable protection\n"
        "• `/nsfw off` – Disable protection\n"
        "• `/scan` – Reply to media to scan\n\n"
        "🚀 Fast • Secure • AI-Powered\n"
        "👨‍💻 Developed by **Team Nexa**"
    )

    await message.reply_text(
        text,
        disable_web_page_preview=True
    )


# =====================================================
# /start → GROUP CHAT
# =====================================================
@Client.on_message(filters.command("start") & filters.group)
async def start_group(client: Client, message: Message):
    await message.reply_text(
        "ℹ️ **Nexa NSFW Bot**\n\n"
        "This command works in **private chat only**.\n"
        "Please DM me to see setup instructions."
    )