"""
Admin commands for user and channel management
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import config, OWNER
from database.models import user_manager, channel_manager
from bot.services.log_channel import LogChannelService
from bot.utils.decorators import admin_only, authorized_only
from bot.utils.helpers import format_user_info, format_file_size
import asyncio

class AdminCommands:
    def __init__(self, bot: Client, log_service: LogChannelService):
        self.bot = bot
        self.log_service = log_service
        self.register_handlers()
    
    def register_handlers(self):
        """Register all admin command handlers"""
        
        @self.bot.on_message(filters.command(["add_user", "addauth"]) & filters.private)
        @admin_only
        async def add_user_command(client: Client, message: Message):
            await self.handle_add_user(message)
        
        @self.bot.on_message(filters.command(["remove_user", "remauth"]) & filters.private)
        @admin_only
        async def remove_user_command(client: Client, message: Message):
            await self.handle_remove_user(message)
        
        @self.bot.on_message(filters.command("users") & filters.private)
        @admin_only
        async def list_users_command(client: Client, message: Message):
            await self.handle_list_users(message)
        
        @self.bot.on_message(filters.command(["add_channel", "addchnl"]) & filters.private)
        @authorized_only
        async def add_channel_command(client: Client, message: Message):
            await self.handle_add_channel(message)
        
        @self.bot.on_message(filters.command(["remove_channel", "remchnl"]) & filters.private)
        @authorized_only
        async def remove_channel_command(client: Client, message: Message):
            await self.handle_remove_channel(message)
        
        @self.bot.on_message(filters.command("channels") & filters.private)
        @admin_only
        async def list_channels_command(client: Client, message: Message):
            await self.handle_list_channels(message)
        
        @self.bot.on_message(filters.command(["add_log_channel"]) & filters.private)
        @admin_only
        async def add_log_channel_command(client: Client, message: Message):
            await self.handle_add_log_channel(message)
        
        @self.bot.on_message(filters.command(["remove_log_channel"]) & filters.private)
        @admin_only
        async def remove_log_channel_command(client: Client, message: Message):
            await self.handle_remove_log_channel(message)
        
        @self.bot.on_message(filters.command(["log_channels"]) & filters.private)
        @admin_only
        async def list_log_channels_command(client: Client, message: Message):
            await self.handle_list_log_channels(message)
        
        @self.bot.on_message(filters.command(["admin_panel", "panel"]) & filters.private)
        @admin_only
        async def admin_panel_command(client: Client, message: Message):
            await self.handle_admin_panel(message)
    
    async def handle_add_user(self, message: Message):
        """Handle add user command"""
        try:
            if len(message.command) < 2:
                await message.reply_text(
                    "❌ **Usage:** `/add_user <user_id>`\n"
                    "**Example:** `/add_user 123456789`"
                )
                return
            
            user_id = int(message.command[1])
            
            # Get user info from Telegram
            try:
                user = await self.bot.get_users(user_id)
                username = user.username
                first_name = user.first_name
                last_name = user.last_name
            except:
                username = None
                first_name = None
                last_name = None
            
            # Add to database
            success = await user_manager.add_user(
                user_id, username, first_name, last_name, message.from_user.id
            )
            
            if success:
                user_info = format_user_info(user_id, username, first_name, last_name)
                await message.reply_text(
                    f"✅ **User Added Successfully**\n\n"
                    f"{user_info}\n"
                    f"**Added by:** {message.from_user.mention}\n"
                    f"**Time:** {message.date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                await message.reply_text("❌ Failed to add user to database.")
                
        except ValueError:
            await message.reply_text("❌ Invalid user ID. Please provide a valid number.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_remove_user(self, message: Message):
        """Handle remove user command"""
        try:
            if len(message.command) < 2:
                await message.reply_text(
                    "❌ **Usage:** `/remove_user <user_id>`\n"
                    "**Example:** `/remove_user 123456789`"
                )
                return
            
            user_id = int(message.command[1])
            
            # Check if user exists and is authorized
            is_auth = await user_manager.is_authorized(user_id)
            if not is_auth:
                await message.reply_text("❌ User is not in the authorized list.")
                return
            
            # Remove from database
            success = await user_manager.remove_user(user_id)
            
            if success:
                await message.reply_text(
                    f"✅ **User Removed Successfully**\n\n"
                    f"**User ID:** `{user_id}`\n"
                    f"**Removed by:** {message.from_user.mention}\n"
                    f"**Time:** {message.date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                await message.reply_text("❌ Failed to remove user from database.")
                
        except ValueError:
            await message.reply_text("❌ Invalid user ID. Please provide a valid number.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_list_users(self, message: Message):
        """Handle list users command"""
        try:
            authorized_users = await user_manager.get_authorized_users()
            
            if not authorized_users:
                await message.reply_text("📝 No authorized users found.")
                return
            
            # Create user list with details
            user_list = ["👥 **Authorized Users:**\n"]
            
            for i, user_id in enumerate(authorized_users, 1):
                try:
                    user = await self.bot.get_users(user_id)
                    user_info = format_user_info(user_id, user.username, user.first_name, user.last_name)
                    user_list.append(f"{i}. {user_info}")
                except:
                    user_list.append(f"{i}. **User ID:** `{user_id}` (Info not available)")
            
            # Split into chunks if too long
            text = "\n".join(user_list)
            if len(text) > 4000:
                chunks = [user_list[i:i+20] for i in range(0, len(user_list), 20)]
                for chunk in chunks:
                    await message.reply_text("\n".join(chunk))
            else:
                await message.reply_text(text)
                
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_add_log_channel(self, message: Message):
        """Handle add log channel command"""
        try:
            if len(message.command) < 2:
                await message.reply_text(
                    "❌ **Usage:** `/add_log_channel <channel_id>`\n"
                    "**Example:** `/add_log_channel -1001234567890`\n\n"
                    "**Note:** Make sure the bot is admin in the channel!"
                )
                return
            
            channel_id = int(message.command[1])
            
            if not str(channel_id).startswith("-100"):
                await message.reply_text("❌ Invalid channel ID. Channel IDs must start with -100.")
                return
            
            # Add log channel
            success = await self.log_service.add_log_channel(channel_id)
            
            if success:
                await message.reply_text(
                    f"✅ **Log Channel Added Successfully**\n\n"
                    f"**Channel ID:** `{channel_id}`\n"
                    f"**Added by:** {message.from_user.mention}\n"
                    f"**Time:** {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"📝 All uploaded files will now be copied to this channel."
                )
            else:
                await message.reply_text(
                    "❌ Failed to add log channel. Please ensure:\n"
                    "• The bot is added to the channel\n"
                    "• The bot has admin permissions\n"
                    "• The channel ID is correct"
                )
                
        except ValueError:
            await message.reply_text("❌ Invalid channel ID. Please provide a valid number.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_remove_log_channel(self, message: Message):
        """Handle remove log channel command"""
        try:
            if len(message.command) < 2:
                await message.reply_text(
                    "❌ **Usage:** `/remove_log_channel <channel_id>`\n"
                    "**Example:** `/remove_log_channel -1001234567890`"
                )
                return
            
            channel_id = int(message.command[1])
            
            # Remove log channel
            success = await self.log_service.remove_log_channel(channel_id)
            
            if success:
                await message.reply_text(
                    f"✅ **Log Channel Removed Successfully**\n\n"
                    f"**Channel ID:** `{channel_id}`\n"
                    f"**Removed by:** {message.from_user.mention}\n"
                    f"**Time:** {message.date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                await message.reply_text("❌ Failed to remove log channel.")
                
        except ValueError:
            await message.reply_text("❌ Invalid channel ID. Please provide a valid number.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_list_log_channels(self, message: Message):
        """Handle list log channels command"""
        try:
            stats = await self.log_service.get_log_channel_stats()
            
            if not stats["enabled"]:
                await message.reply_text("📝 Log channel service is disabled.")
                return
            
            text_parts = [
                "📝 **Log Channel Status:**\n",
                f"**Status:** {'🟢 Enabled' if stats['enabled'] else '🔴 Disabled'}",
                f"**Total Channels:** {stats['total_channels']}",
                f"**Active Channels:** {stats['active_channels']}",
                f"**Failed Channels:** {stats['failed_channels']}\n"
            ]
            
            if stats["log_channels"]:
                text_parts.append("**Active Log Channels:**")
                for i, channel_id in enumerate(stats["log_channels"], 1):
                    try:
                        chat = await self.bot.get_chat(channel_id)
                        status = "🔴 Failed" if channel_id in stats["failed_channel_ids"] else "🟢 Active"
                        text_parts.append(f"{i}. {chat.title} (`{channel_id}`) - {status}")
                    except:
                        text_parts.append(f"{i}. `{channel_id}` - 🔴 Not Accessible")
            
            await message.reply_text("\n".join(text_parts))
            
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_admin_panel(self, message: Message):
        """Handle admin panel command"""
        try:
            # Get statistics
            authorized_users = await user_manager.get_authorized_users()
            authorized_channels = await channel_manager.get_authorized_channels()
            log_stats = await self.log_service.get_log_channel_stats()
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👥 Users", callback_data="admin_users"),
                    InlineKeyboardButton("📁 Channels", callback_data="admin_channels")
                ],
                [
                    InlineKeyboardButton("📝 Log Channels", callback_data="admin_log_channels"),
                    InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")
                ],
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
                    InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")
                ]
            ])
            
            text = (
                f"🎛️ **Admin Panel**\n\n"
                f"👥 **Authorized Users:** {len(authorized_users)}\n"
                f"📁 **Authorized Channels:** {len(authorized_channels)}\n"
                f"📝 **Log Channels:** {log_stats['total_channels']} "
                f"({'🟢 Active' if log_stats['enabled'] else '🔴 Disabled'})\n"
                f"🤖 **Bot Status:** 🟢 Running\n\n"
                f"**Select an option below:**"
            )
            
            await message.reply_text(text, reply_markup=keyboard)
            
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    # Add other handler methods for channels, etc.
    async def handle_add_channel(self, message: Message):
        """Handle add channel command (existing functionality)"""
        # Implementation similar to existing code but with database integration
        pass
    
    async def handle_remove_channel(self, message: Message):
        """Handle remove channel command (existing functionality)"""
        # Implementation similar to existing code but with database integration
        pass
    
    async def handle_list_channels(self, message: Message):
        """Handle list channels command (existing functionality)"""
        # Implementation similar to existing code but with database integration
        pass
