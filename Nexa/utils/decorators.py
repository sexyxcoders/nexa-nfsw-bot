from functools import wraps
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.types import Message


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply_text("❌ Group only command")

        if not message.from_user:
            return await message.reply_text("❌ Anonymous admins not supported")

        bot = await client.get_chat_member(message.chat.id, "me")
        if bot.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply_text("❌ I must be admin")

        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply_text("❌ Admins only")

        return await func(client, message, *args, **kwargs)

    return wrapper


# backward compatibility
AdminRights = admin_only