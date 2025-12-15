from functools import wraps
from pyrogram.types import Message

def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message):
        member = await client.get_chat_member(
            message.chat.id,
            message.from_user.id
        )
        if member.status not in ("administrator", "creator"):
            await message.reply("❌ Only group admins can use this.")
            return
        return await func(client, message)
    return wrapper