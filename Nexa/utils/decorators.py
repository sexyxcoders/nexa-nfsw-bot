from functools import wraps
from pyrogram.types import Message
from pyrogram.errors import ChatAdminRequired

def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        # Must be group
        if message.chat.type not in ("group", "supergroup"):
            return await message.reply("❌ This command works only in groups.")

        # Anonymous admin support
        if message.sender_chat:
            return await func(client, message, *args, **kwargs)

        user = message.from_user
        if not user:
            return await message.reply("❌ Only group admins can use this.")

        try:
            member = await client.get_chat_member(message.chat.id, user.id)
        except ChatAdminRequired:
            return await message.reply("❌ Bot needs admin rights.")
        except Exception:
            return await message.reply("❌ Only group admins can use this.")

        # Allow creator or admin
        if member.status in ("administrator", "creator"):
            return await func(client, message, *args, **kwargs)

        return await message.reply("❌ Only group admins can use this.")

    return wrapper