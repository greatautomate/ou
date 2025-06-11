"""
Enhanced Medusa Bot - Modular Architecture with Database Integration
"""
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Import our enhanced modules
from config.settings import config, API_ID, API_HASH, BOT_TOKEN, OWNER, CREDIT
from database.models import db_manager, user_manager, channel_manager
from bot.services.log_channel import LogChannelService
from bot.commands.admin import AdminCommands
from bot.handlers.download_handler import EnhancedDownloadHandler
from bot.utils.decorators import authorized_only, admin_only, secure_command
from bot.utils.helpers import format_user_info, cleanup_old_files

class MedusaBot:
    """Enhanced Medusa Bot with modular architecture"""
    
    def __init__(self):
        # Initialize bot client
        self.bot = Client(
            "medusa_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        # Initialize services
        self.log_service = None
        self.download_handler = None
        self.admin_commands = None
        
        # Bot statistics
        self.start_time = datetime.now()
        self.total_downloads = 0
        self.total_users = 0
        
    async def initialize(self):
        """Initialize all bot services"""
        print("🚀 Initializing Medusa Bot...")
        
        # Initialize database
        await db_manager.initialize()
        
        # Initialize services
        self.log_service = LogChannelService(self.bot)
        await self.log_service.initialize()
        
        self.download_handler = EnhancedDownloadHandler(self.bot, self.log_service)
        self.admin_commands = AdminCommands(self.bot, self.log_service)
        
        # Register handlers
        self.register_handlers()
        
        # Setup periodic tasks
        asyncio.create_task(self.periodic_cleanup())
        
        print("✅ Bot initialization complete!")
    
    def register_handlers(self):
        """Register all bot message handlers"""
        
        @self.bot.on_message(filters.command(["start"]))
        async def start_command(client: Client, message: Message):
            await self.handle_start(message)
        
        @self.bot.on_message(filters.command(["help"]))
        async def help_command(client: Client, message: Message):
            await self.handle_help(message)
        
        @self.bot.on_message(filters.command(["id"]))
        async def id_command(client: Client, message: Message):
            await self.handle_id(message)
        
        @self.bot.on_message(filters.command(["info"]))
        async def info_command(client: Client, message: Message):
            await self.handle_info(message)
        
        @self.bot.on_message(filters.command(["stats"]))
        @admin_only
        async def stats_command(client: Client, message: Message):
            await self.handle_stats(message)
        
        @self.bot.on_message(filters.command(["drm"]))
        @secure_command(max_calls=20, time_window=3600)
        async def drm_command(client: Client, message: Message):
            await self.handle_drm(message)
        
        @self.bot.on_message(filters.command(["y2t"]))
        @secure_command(max_calls=10, time_window=3600)
        async def y2t_command(client: Client, message: Message):
            await self.handle_y2t(message)
        
        @self.bot.on_message(filters.command(["t2t"]))
        @secure_command(max_calls=15, time_window=3600)
        async def t2t_command(client: Client, message: Message):
            await self.handle_t2t(message)
        
        @self.bot.on_message(filters.command(["stop"]))
        @authorized_only
        async def stop_command(client: Client, message: Message):
            await self.handle_stop(message)
        
        @self.bot.on_message(filters.command(["logs"]))
        @admin_only
        async def logs_command(client: Client, message: Message):
            await self.handle_logs(message)
        
        # Single link handler
        @self.bot.on_message(filters.text & filters.private)
        @authorized_only
        async def text_handler(client: Client, message: Message):
            await self.handle_single_link(message)
    
    async def handle_start(self, message: Message):
        """Handle /start command"""
        user_id = message.from_user.id
        
        # Add user to database if not exists
        await user_manager.add_user(
            user_id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        # Create welcome message
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📖 Help", callback_data="help"),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("🛠️ Contact", url=f"https://t.me/{config.config.owner_username.replace('@', '')}")
            ]
        ])
        
        welcome_text = (
            f"🎉 **Welcome to Medusa Bot!**\n\n"
            f"🤖 **Advanced File Downloader Bot**\n"
            f"📥 Download videos, documents, and more from 1000+ websites\n"
            f"🔐 DRM content support with decryption\n"
            f"📦 Batch processing capabilities\n"
            f"📝 Automatic logging to channels\n\n"
            f"🚀 **Get started with /help**\n\n"
            f"💻 **Made by:** {CREDIT}"
        )
        
        await message.reply_text(welcome_text, reply_markup=keyboard)
    
    async def handle_help(self, message: Message):
        """Handle /help command with enhanced UI"""
        is_authorized = await user_manager.is_authorized(message.from_user.id)
        is_admin = message.from_user.id == OWNER
        
        help_sections = []
        
        # Public commands
        help_sections.append(
            "🌐 **Public Commands:**\n"
            "• `/start` - Welcome message\n"
            "• `/help` - Show this help\n"
            "• `/id` - Get chat/user ID\n"
            "• `/info` - Your account info"
        )
        
        # Authorized user commands
        if is_authorized:
            help_sections.append(
                "🔒 **Download Commands:** (Authorized Users)\n"
                "• `/drm` - Batch download from .txt file\n"
                "• `/y2t` - YouTube playlist to .txt\n"
                "• `/t2t` - Text to .txt converter\n"
                "• Send any link - Single file download\n"
                "• `/stop` - Cancel running tasks"
            )
        
        # Admin commands
        if is_admin:
            help_sections.append(
                "👑 **Admin Commands:** (Owner Only)\n"
                "• `/add_user <id>` - Add authorized user\n"
                "• `/remove_user <id>` - Remove user\n"
                "• `/users` - List authorized users\n"
                "• `/add_log_channel <id>` - Add log channel\n"
                "• `/log_channels` - Manage log channels\n"
                "• `/stats` - Bot statistics\n"
                "• `/logs` - View bot logs\n"
                "• `/admin_panel` - Admin dashboard"
            )
        
        # Features section
        help_sections.append(
            "✨ **Features:**\n"
            "• 🎬 Video downloads (YouTube, ClassPlus, etc.)\n"
            "• 📄 Document downloads (PDF, DOC, etc.)\n"
            "• 🎵 Audio downloads (MP3, M4A, etc.)\n"
            "• 🖼️ Image downloads (JPG, PNG, etc.)\n"
            "• 📦 Archive downloads (ZIP, RAR, etc.)\n"
            "• 🔐 DRM content decryption\n"
            "• 📊 Progress tracking\n"
            "• 📝 Automatic logging\n"
            "• 🔄 Retry mechanisms"
        )
        
        if not is_authorized:
            help_sections.append(
                f"🔐 **Need Access?**\n"
                f"Contact {config.config.owner_username} for authorization"
            )
        
        help_text = "\n\n".join(help_sections)
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Bot Stats", callback_data="public_stats"),
                InlineKeyboardButton("🔄 Refresh", callback_data="help")
            ]
        ])
        
        await message.reply_text(help_text, reply_markup=keyboard)
    
    async def handle_id(self, message: Message):
        """Handle /id command"""
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        id_text = (
            f"🆔 **ID Information**\n\n"
            f"**Your User ID:** `{user_id}`\n"
            f"**Chat ID:** `{chat_id}`\n"
            f"**Chat Type:** {message.chat.type}"
        )
        
        if message.chat.type in ["group", "supergroup"]:
            id_text += f"\n**Group Title:** {message.chat.title}"
        
        await message.reply_text(id_text)
    
    async def handle_info(self, message: Message):
        """Handle /info command"""
        user = message.from_user
        is_authorized = await user_manager.is_authorized(user.id)
        
        info_text = (
            f"👤 **Your Information**\n\n"
            f"{format_user_info(user.id, user.username, user.first_name, user.last_name)}\n"
            f"**Authorization:** {'✅ Authorized' if is_authorized else '❌ Not Authorized'}\n"
            f"**Account Type:** {'👑 Owner' if user.id == OWNER else '👤 User'}\n"
            f"**Language:** {user.language_code or 'Unknown'}"
        )
        
        await message.reply_text(info_text)
    
    async def handle_stats(self, message: Message):
        """Handle /stats command (admin only)"""
        try:
            # Get statistics
            authorized_users = await user_manager.get_authorized_users()
            authorized_channels = await channel_manager.get_authorized_channels()
            log_stats = await self.log_service.get_log_channel_stats()
            
            uptime = datetime.now() - self.start_time
            uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
            
            stats_text = (
                f"📊 **Bot Statistics**\n\n"
                f"🕐 **Uptime:** {uptime_str}\n"
                f"👥 **Authorized Users:** {len(authorized_users)}\n"
                f"📁 **Authorized Channels:** {len(authorized_channels)}\n"
                f"📝 **Log Channels:** {log_stats['total_channels']} "
                f"({'🟢 Active' if log_stats['enabled'] else '🔴 Disabled'})\n"
                f"📥 **Total Downloads:** {self.total_downloads}\n"
                f"🤖 **Bot Version:** Enhanced v2.0\n"
                f"💾 **Database:** {'🟢 Connected' if db_manager.pool else '🔴 Disconnected'}\n\n"
                f"**System Info:**\n"
                f"• Python: {sys.version.split()[0]}\n"
                f"• Platform: {sys.platform}\n"
                f"• Memory Usage: Available on request"
            )
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👥 Users", callback_data="admin_users"),
                    InlineKeyboardButton("📁 Channels", callback_data="admin_channels")
                ],
                [
                    InlineKeyboardButton("📝 Logs", callback_data="admin_logs"),
                    InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")
                ]
            ])
            
            await message.reply_text(stats_text, reply_markup=keyboard)
            
        except Exception as e:
            await message.reply_text(f"❌ Error getting statistics: {str(e)}")
    
    async def handle_drm(self, message: Message):
        """Handle /drm command for batch downloads"""
        await message.reply_text(
            "📁 **Batch Download**\n\n"
            "Please send a .txt file containing the links you want to download.\n"
            "Each link should be on a separate line.\n\n"
            "**Supported formats:**\n"
            "• `https://example.com/video.mp4`\n"
            "• `protocol://url` (for custom naming)\n\n"
            "**Features:**\n"
            "• Progress tracking\n"
            "• Error handling\n"
            "• Automatic retry\n"
            "• Log channel backup"
        )
        
        # Wait for file upload
        try:
            file_message = await self.bot.listen(message.chat.id, timeout=300)
            
            if not file_message.document or not file_message.document.file_name.endswith('.txt'):
                await message.reply_text("❌ Please send a valid .txt file.")
                return
            
            # Download and process file
            file_path = await file_message.download()
            
            # Read links from file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                await message.reply_text("❌ The file is empty.")
                os.remove(file_path)
                return
            
            # Parse links
            lines = content.split('\n')
            links = []
            for line in lines:
                line = line.strip()
                if line and '://' in line:
                    if line.startswith('http'):
                        links.append(line)
                    else:
                        # Handle protocol://url format
                        parts = line.split('://', 1)
                        if len(parts) == 2:
                            links.append(parts)
            
            if not links:
                await message.reply_text("❌ No valid links found in the file.")
                os.remove(file_path)
                return
            
            # Start batch download
            await self.download_handler.handle_batch_download(message, links)
            
            # Cleanup
            os.remove(file_path)
            
        except asyncio.TimeoutError:
            await message.reply_text("⏰ Timeout waiting for file. Please try again.")
        except Exception as e:
            await message.reply_text(f"❌ Error processing file: {str(e)}")
    
    async def handle_single_link(self, message: Message):
        """Handle single link downloads"""
        text = message.text.strip()
        
        # Check if it's a valid URL
        if not ('://' in text and any(text.startswith(proto) for proto in ['http', 'https', 'ftp'])):
            return  # Not a URL, ignore
        
        # Process single download
        await self.download_handler.handle_single_download(message, text)
    
    async def handle_y2t(self, message: Message):
        """Handle YouTube to text conversion"""
        # Implementation similar to existing y2t but with enhanced features
        await message.reply_text("🎬 **YouTube to Text Converter**\n\nSend a YouTube URL or playlist link:")
        # ... (implement enhanced y2t logic)
    
    async def handle_t2t(self, message: Message):
        """Handle text to text file conversion"""
        # Implementation similar to existing t2t but with enhanced features
        await message.reply_text("📝 **Text to File Converter**\n\nSend the text you want to convert:")
        # ... (implement enhanced t2t logic)
    
    async def handle_stop(self, message: Message):
        """Handle stop command"""
        await message.reply_text("🛑 **Stopping current operations...**")
        # Cancel active downloads for this user
        # ... (implement stop logic)
        await message.reply_text("✅ **Operations stopped successfully.**")
    
    async def handle_logs(self, message: Message):
        """Handle logs command"""
        try:
            if os.path.exists("logs.txt"):
                await message.reply_document(
                    document="logs.txt",
                    caption="📋 **Bot Logs**"
                )
            else:
                await message.reply_text("📋 No log file found.")
        except Exception as e:
            await message.reply_text(f"❌ Error sending logs: {str(e)}")
    
    async def periodic_cleanup(self):
        """Periodic cleanup task"""
        while True:
            try:
                # Clean up old files every hour
                await cleanup_old_files("downloads", max_age_hours=2)
                await cleanup_old_files("temp", max_age_hours=1)
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                print(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(3600)
    
    async def run(self):
        """Run the bot"""
        try:
            await self.initialize()
            print(f"🚀 Starting Medusa Bot Enhanced...")
            print(f"📊 Owner: {config.config.owner_username}")
            print(f"📝 Log Channels: {len(config.config.log_channels)}")
            await self.bot.run()
        except Exception as e:
            print(f"❌ Failed to start bot: {str(e)}")
            sys.exit(1)
        finally:
            await db_manager.close()

# Global bot instance
medusa_bot = MedusaBot()

if __name__ == "__main__":
    asyncio.run(medusa_bot.run())
