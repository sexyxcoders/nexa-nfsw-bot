# Nexa/utils/decorators.py
# =====================================================
# Nexa Bot Decorators (Pyrogram v2 Compatible)
# =====================================================

from functools import wraps
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus


# =====================================================
# Helpers
# =====================================================

def _is_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


# =====================================================
# Group Only
# =====================================================

def group_only(func=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):
            if not _is_group(message):
                return await message.reply("❌ This command works only in groups.")
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator(func) if func else decorator


# =====================================================
# Private Only
# =====================================================

def private_only(func=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):
            if message.chat.type != ChatType.PRIVATE:
                return await message.reply("❌ This command works only in private chat.")
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator(func) if func else decorator


# =====================================================
# Owner Only
# =====================================================

def owner_only(func=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):
            owner_id = getattr(client, "OWNER_ID", None)

            if not owner_id:
                return await message.reply("❌ OWNER_ID not configured.")

            if not message.from_user or message.from_user.id != owner_id:
                return await message.reply("❌ Only bot owner can use this command.")

            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator(func) if func else decorator


# =====================================================
# Sudo Only
# =====================================================

def sudo_only(func=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):
            sudo_users = getattr(client, "SUDO_USERS", [])

            if not message.from_user or message.from_user.id not in sudo_users:
                return await message.reply("❌ You are not a sudo user.")

            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator(func) if func else decorator


# =====================================================
# Admin Only (Group Admins)
# =====================================================

def admin_only(func=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):

            # ── Group check
            if not _is_group(message):
                return await message.reply("❌ This command works only in groups.")

            # ── Anonymous admin check
            if message.from_user is None:
                return await message.reply(
                    "❌ Anonymous admins are not supported.\n"
                    "➡ Disable anonymous admin mode and try again."
                )

            # ── Bot admin check
            try:
                bot_member = await client.get_chat_member(message.chat.id, "me")
                if bot_member.status not in (
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.OWNER,
                ):
                    return await message.reply(
                        "❌ I must be admin to check permissions."
                    )
            except Exception:
                return await message.reply("❌ Failed to verify bot permissions.")

            # ── User admin check
            try:
                user_member = await client.get_chat_member(
                    message.chat.id,
                    message.from_user.id
                )
            except Exception:
                return await message.reply("❌ Failed to verify admin status.")

            if user_member.status not in (
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                return await message.reply("❌ Only group admins can use this command.")

            return await func(client, message, *args, **kwargs)

        return wrapper

    # Supports both @admin_only and @admin_only()
    return decorator(func) if func else decorator


# =====================================================
# Backward Compatibility (DO NOT REMOVE)
# =====================================================

AdminRights = admin_only