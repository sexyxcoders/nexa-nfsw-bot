from functools import wraps
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.types import Message


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):

        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply("❌ Group only command")

        if not message.from_user:
            return await message.reply("❌ Anonymous admins not supported")

        bot = await client.get_chat_member(message.chat.id, "me")
        if bot.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply("❌ I must be admin")

        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply("❌ Admins only")

        return await func(client, message, *args, **kwargs)

    return wrapper


# BACKWARD COMPATIBILITY
AdminRights = admin_only