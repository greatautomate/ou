"""
Decorators for bot command handlers
"""
import functools
from typing import Callable, Any
from pyrogram.types import Message
from config.settings import config, OWNER
from database.models import user_manager
import asyncio
from datetime import datetime, timedelta

def admin_only(func: Callable) -> Callable:
    """Decorator to restrict commands to bot owner only"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.from_user.id != OWNER:
            await message.reply_text(
                "❌ **Access Denied**\n\n"
                f"This command is restricted to the bot owner only.\n"
                f"Contact {config.config.owner_username} for assistance."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper

def authorized_only(func: Callable) -> Callable:
    """Decorator to restrict commands to authorized users only"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        # Check if user is authorized
        is_authorized = await user_manager.is_authorized(message.from_user.id)
        
        if not is_authorized:
            await message.reply_text(
                f"❌ **Access Denied**\n\n"
                f"You are not authorized to use this command.\n"
                f"Contact the bot owner {config.config.owner_username} for access."
            )
            return
        
        # Update user activity
        await user_manager.update_activity(message.from_user.id)
        
        return await func(client, message, *args, **kwargs)
    return wrapper

def rate_limit(max_calls: int = 10, time_window: int = 3600):
    """
    Rate limiting decorator
    
    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window in seconds (default: 1 hour)
    """
    user_calls = {}
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(client, message: Message, *args, **kwargs):
            user_id = message.from_user.id
            current_time = datetime.now()
            
            # Clean old entries
            if user_id in user_calls:
                user_calls[user_id] = [
                    call_time for call_time in user_calls[user_id]
                    if current_time - call_time < timedelta(seconds=time_window)
                ]
            else:
                user_calls[user_id] = []
            
            # Check rate limit
            if len(user_calls[user_id]) >= max_calls:
                remaining_time = time_window - (current_time - user_calls[user_id][0]).seconds
                await message.reply_text(
                    f"⏰ **Rate Limit Exceeded**\n\n"
                    f"You can use this command again in {remaining_time // 60} minutes and {remaining_time % 60} seconds.\n"
                    f"**Limit:** {max_calls} calls per {time_window // 3600} hour(s)"
                )
                return
            
            # Record this call
            user_calls[user_id].append(current_time)
            
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator

def typing_action(func: Callable) -> Callable:
    """Decorator to show typing action while processing"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        # Start typing action
        typing_task = asyncio.create_task(
            client.send_chat_action(message.chat.id, "typing")
        )
        
        try:
            result = await func(client, message, *args, **kwargs)
            return result
        finally:
            # Stop typing action
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass
    
    return wrapper

def error_handler(func: Callable) -> Callable:
    """Decorator to handle errors gracefully"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except Exception as e:
            error_message = (
                f"❌ **An error occurred:**\n\n"
                f"```\n{str(e)}\n```\n\n"
                f"Please try again or contact {config.config.owner_username} if the problem persists."
            )
            
            try:
                await message.reply_text(error_message)
            except:
                # If we can't send the error message, at least log it
                print(f"Error in {func.__name__}: {e}")
            
            # Log error for debugging
            print(f"Error in {func.__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    return wrapper

def log_command_usage(func: Callable) -> Callable:
    """Decorator to log command usage for analytics"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        # Log command usage
        command = message.command[0] if message.command else "unknown"
        user_id = message.from_user.id
        username = message.from_user.username
        timestamp = datetime.now()
        
        print(f"📊 Command used: /{command} by {username} ({user_id}) at {timestamp}")
        
        # Could extend this to store in database for analytics
        if config.config.enable_analytics:
            # TODO: Store in analytics table
            pass
        
        return await func(client, message, *args, **kwargs)
    
    return wrapper

def require_reply_to_file(func: Callable) -> Callable:
    """Decorator to ensure command is used as reply to a file"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if not message.reply_to_message:
            await message.reply_text(
                "❌ **Please reply to a file**\n\n"
                "This command must be used as a reply to a file message."
            )
            return
        
        reply_msg = message.reply_to_message
        if not (reply_msg.document or reply_msg.video or reply_msg.audio or reply_msg.photo):
            await message.reply_text(
                "❌ **No file found**\n\n"
                "Please reply to a message containing a file."
            )
            return
        
        return await func(client, message, *args, **kwargs)
    
    return wrapper

def channel_only(func: Callable) -> Callable:
    """Decorator to restrict commands to channels only"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.chat.type not in ["channel", "supergroup"]:
            await message.reply_text(
                "❌ **Channel Only Command**\n\n"
                "This command can only be used in channels or supergroups."
            )
            return
        
        return await func(client, message, *args, **kwargs)
    
    return wrapper

def private_only(func: Callable) -> Callable:
    """Decorator to restrict commands to private chats only"""
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.chat.type != "private":
            await message.reply_text(
                "❌ **Private Chat Only**\n\n"
                "This command can only be used in private messages."
            )
            return
        
        return await func(client, message, *args, **kwargs)
    
    return wrapper

# Combine multiple decorators
def secure_command(max_calls: int = 10, time_window: int = 3600):
    """
    Combine authorization, rate limiting, error handling, and logging
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in order
        decorated_func = func
        decorated_func = error_handler(decorated_func)
        decorated_func = log_command_usage(decorated_func)
        decorated_func = rate_limit(max_calls, time_window)(decorated_func)
        decorated_func = authorized_only(decorated_func)
        decorated_func = typing_action(decorated_func)
        
        return decorated_func
    
    return decorator

def admin_command(func: Callable) -> Callable:
    """Combine admin-only, error handling, and logging"""
    decorated_func = func
    decorated_func = error_handler(decorated_func)
    decorated_func = log_command_usage(decorated_func)
    decorated_func = admin_only(decorated_func)
    decorated_func = typing_action(decorated_func)
    
    return decorated_func
