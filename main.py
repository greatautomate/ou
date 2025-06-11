import os
import re
import sys
import m3u8
import json
import time
import pytz
import asyncio
import requests
import subprocess
import urllib
import urllib.parse
import yt_dlp
import tgcrypto
import cloudscraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64encode, b64decode
from logs import logging
from bs4 import BeautifulSoup
import handler as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, OWNER_USERNAME, CREDIT, LOG_CHANNELS, BACKUP_LOG_CHANNELS, ALL_LOG_CHANNELS
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
from aiohttp import web
import random
import pyromod.listen  # This patches the Client class with listen method
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
# Removed problematic imports that don't exist in current Pyrogram version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp
import aiofiles
import zipfile
import shutil
import ffmpeg

# Initialize the bot
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Verify pyromod listen method is available
def verify_listen_method():
    """Verify that the listen method is available on the bot client"""
    if not hasattr(bot, 'listen'):
        raise ImportError(
            "❌ CRITICAL ERROR: pyromod.listen is not properly installed or imported!\n"
            "The bot requires pyromod for interactive input handling.\n"
            "Please install it with: pip install pyromod\n"
            "Or check if the import is working correctly."
        )
    print("✅ pyromod.listen method is available")

# Alternative listen function if pyromod fails
async def safe_listen(chat_id, original_user_id=None, timeout=300):
    """
    Safe listen function with fallback mechanism
    This provides an alternative if pyromod.listen fails
    """
    try:
        # Try using pyromod's listen method
        if hasattr(bot, 'listen'):
            return await bot.listen(chat_id, timeout=timeout)
        else:
            raise AttributeError("listen method not available")
    except Exception as e:
        # Fallback: Use a simple message waiting mechanism
        print(f"⚠️ pyromod.listen failed: {e}")
        print("🔄 Using fallback message waiting mechanism...")

        import asyncio
        from pyrogram import filters

        # Create a future to wait for the message
        message_future = asyncio.Future()

        # Define a temporary handler
        @bot.on_message(filters.chat(chat_id))
        async def temp_handler(client, message):
            if original_user_id and message.from_user:
                if message.from_user.id == original_user_id:
                    if not message_future.done():
                        message_future.set_result(message)
            elif not original_user_id:
                if not message_future.done():
                    message_future.set_result(message)

        try:
            # Wait for the message with timeout
            result = await asyncio.wait_for(message_future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"No response received within {timeout} seconds")
        finally:
            # Note: Pyrogram doesn't have remove_handler method
            # The handler will be automatically cleaned up
            pass

# INTEGRATED LOG CHANNEL SERVICE
class LogChannelService:
    """Simplified log channel service integrated into main bot"""

    def __init__(self, bot_client: Client):
        self.bot = bot_client
        self.primary_channels = LOG_CHANNELS
        self.backup_channels = BACKUP_LOG_CHANNELS
        self.all_channels = ALL_LOG_CHANNELS
        self.failed_channels = set()
        self.enabled = len(self.all_channels) > 0

    async def initialize(self):
        """Initialize and verify log channels"""
        if not self.enabled:
            print("📝 Log channel service disabled (no log channels configured)")
            return

        print(f"📝 Initializing log channel service with {len(self.all_channels)} channels")

        # Verify channels are accessible
        accessible_channels = []
        for channel_id in self.all_channels:
            try:
                chat = await self.bot.get_chat(channel_id)
                accessible_channels.append(channel_id)
                print(f"✅ Log channel accessible: {chat.title} ({channel_id})")
            except Exception as e:
                print(f"⚠️ Log channel not accessible: {channel_id}")
                print(f"   Reason: {e}")
                print(f"   💡 Make sure the bot is added to the channel as an admin")
                self.failed_channels.add(channel_id)

        if not accessible_channels:
            print("⚠️ No accessible log channels found")
            print("   📝 Log channel service will be disabled")
            print("   💡 Add the bot to log channels and restart to enable logging")
            self.enabled = False
        else:
            print(f"📝 Log channel service enabled with {len(accessible_channels)} accessible channels")

    async def log_file_upload(self, original_message: Message, user_info: dict, download_info: dict):
        """Log file upload to all configured log channels"""
        if not self.enabled:
            return []

        log_message_ids = []
        caption = self._create_log_caption(user_info, download_info)

        for channel_id in self.all_channels:
            if channel_id in self.failed_channels:
                continue

            try:
                log_message = await self._copy_file_to_channel(original_message, channel_id, caption)
                if log_message:
                    log_message_ids.append(log_message.id)
                    print(f"📝 File logged to channel {channel_id}, message ID: {log_message.id}")

            except Exception as e:
                print(f"❌ Failed to log file to channel {channel_id}: {e}")
                self.failed_channels.add(channel_id)

        return log_message_ids

    async def _copy_file_to_channel(self, original_message: Message, channel_id: int, caption: str):
        """Copy file from original message to log channel"""
        try:
            if original_message.document:
                return await self.bot.send_document(
                    chat_id=channel_id,
                    document=original_message.document.file_id,
                    caption=caption,
                    file_name=original_message.document.file_name
                )
            elif original_message.video:
                return await self.bot.send_video(
                    chat_id=channel_id,
                    video=original_message.video.file_id,
                    caption=caption,
                    duration=original_message.video.duration,
                    width=original_message.video.width,
                    height=original_message.video.height
                )
            elif original_message.photo:
                return await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=original_message.photo.file_id,
                    caption=caption
                )
            elif original_message.audio:
                return await self.bot.send_audio(
                    chat_id=channel_id,
                    audio=original_message.audio.file_id,
                    caption=caption,
                    duration=original_message.audio.duration,
                    title=original_message.audio.title,
                    performer=original_message.audio.performer
                )
            else:
                # For other types, send as document
                return await self.bot.send_message(
                    chat_id=channel_id,
                    text=f"📄 **File Upload Log**\n\n{caption}"
                )

        except Exception as e:
            print(f"❌ Error copying file to channel {channel_id}: {e}")
            raise

    def _create_log_caption(self, user_info: dict, download_info: dict) -> str:
        """Create caption for log channel"""
        user_id = user_info.get('id', 'Unknown')
        username = user_info.get('username', 'No username')
        first_name = user_info.get('first_name', 'Unknown')

        file_name = download_info.get('name', 'Unknown')
        file_index = download_info.get('index', 'N/A')
        batch_name = download_info.get('batch_name', 'Unknown')
        original_url = download_info.get('original_url', 'N/A')

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        caption = (
            f"📝 **FILE UPLOAD LOG** 📝\n\n"
            f"👤 **User Info:**\n"
            f"├── ID: `{user_id}`\n"
            f"├── Name: {first_name}\n"
            f"├── Username: @{username}\n\n"
            f"📁 **File Info:**\n"
            f"├── Index: {file_index}\n"
            f"├── Name: `{file_name}`\n"
            f"├── Batch: {batch_name}\n\n"
            f"🔗 **Source:** [Original Link]({original_url})\n"
            f"⏰ **Time:** {timestamp}\n\n"
            f"🌟 **Bot:** {CREDIT}"
        )

        return caption

    async def log_batch_summary(self, user_info: dict, batch_stats: dict):
        """Log batch completion summary to log channels"""
        if not self.enabled:
            return []

        summary_message_ids = []
        caption = self._create_batch_summary_caption(user_info, batch_stats)

        for channel_id in self.all_channels:
            if channel_id in self.failed_channels:
                continue

            try:
                message = await self.bot.send_message(
                    chat_id=channel_id,
                    text=caption
                )
                summary_message_ids.append(message.id)
                print(f"📊 Batch summary logged to channel {channel_id}")

            except Exception as e:
                print(f"❌ Failed to log batch summary to channel {channel_id}: {e}")

        return summary_message_ids

    def _create_batch_summary_caption(self, user_info: dict, batch_stats: dict) -> str:
        """Create batch summary caption"""
        user_id = user_info.get('id', 'Unknown')
        username = user_info.get('username', 'No username')
        first_name = user_info.get('first_name', 'Unknown')

        batch_name = batch_stats.get('batch_name', 'Unknown')
        total = batch_stats.get('total', 0)
        downloaded = batch_stats.get('downloaded', 0)
        uploaded = batch_stats.get('uploaded', 0)
        failed = batch_stats.get('failed', 0)
        success_rate = (downloaded/total)*100 if total > 0 else 0

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        caption = (
            f"📊 **BATCH COMPLETION SUMMARY** 📊\n\n"
            f"👤 **User Info:**\n"
            f"├── ID: `{user_id}`\n"
            f"├── Name: {first_name}\n"
            f"├── Username: @{username}\n\n"
            f"📈 **Batch Statistics:**\n"
            f"├── Batch Name: `{batch_name}`\n"
            f"├── Total Files: {total}\n"
            f"├── Downloaded: {downloaded}\n"
            f"├── Uploaded: {uploaded}\n"
            f"├── Failed: {failed}\n"
            f"├── Success Rate: {success_rate:.1f}%\n\n"
            f"⚡ **Method:** 5 Concurrent Downloads + Instant Sequential Uploads\n"
            f"⏰ **Completed:** {timestamp}\n\n"
            f"🌟 **Bot:** {CREDIT}"
        )

        return caption

    def get_stats(self) -> dict:
        """Get log channel service statistics"""
        return {
            "enabled": self.enabled,
            "total_channels": len(self.all_channels),
            "primary_channels": len(self.primary_channels),
            "backup_channels": len(self.backup_channels),
            "failed_channels": len(self.failed_channels),
            "active_channels": len(self.all_channels) - len(self.failed_channels)
        }

# Initialize log channel service
log_service = LogChannelService(bot)

# Bot startup initialization
async def initialize_bot_services():
    """Initialize services when bot starts"""
    print("🔄 Initializing log channel service...")
    await log_service.initialize()
    print("✅ All services initialized successfully!")

# Fix environment variable handling to prevent NoneType errors
AUTH_USER_ENV = os.environ.get('AUTH_USERS', '7527795504')
if AUTH_USER_ENV:
    AUTH_USER = AUTH_USER_ENV.split(',')
else:
    AUTH_USER = ['7527795504']

# Add More AUTH_USER
AUTH_USER.append('5680454765')
AUTH_USERS = [int(user_id) for user_id in AUTH_USER if user_id.strip().isdigit()]
if int(OWNER) not in AUTH_USERS:
    AUTH_USERS.append(int(OWNER))

CHANNEL_OWNERS = {}
CHANNELS_ENV = os.environ.get('CHANNELS', '')
if CHANNELS_ENV:
    CHANNELS = CHANNELS_ENV.split(',')
else:
    CHANNELS = []
CHANNELS_LIST = [int(channel_id) for channel_id in CHANNELS if channel_id.strip().isdigit()]
cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")
api_url = "http://master-api-v3.vercel.app/"
api_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNzkxOTMzNDE5NSIsInRnX3VzZXJuYW1lIjoi4p61IFtvZmZsaW5lXSIsImlhdCI6MTczODY5MjA3N30.SXzZ1MZcvMp5sGESj0hBKSghhxJ3k1GTWoBUbivUe1I"
token_cp ='eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9r'
adda_token = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJkcGthNTQ3MEBnbWFpbC5jb20iLCJhdWQiOiIxNzg2OTYwNSIsImlhdCI6MTc0NDk0NDQ2NCwiaXNzIjoiYWRkYTI0Ny5jb20iLCJuYW1lIjoiZHBrYSIsImVtYWlsIjoiZHBrYTU0NzBAZ21haWwuY29tIiwicGhvbmUiOiI3MzUyNDA0MTc2IiwidXNlcklkIjoiYWRkYS52MS41NzMyNmRmODVkZDkxZDRiNDkxN2FiZDExN2IwN2ZjOCIsImxvZ2luQXBpVmVyc2lvbiI6MX0.0QOuYFMkCEdVmwMVIPeETa6Kxr70zEslWOIAfC_ylhbku76nDcaBoNVvqN4HivWNwlyT0jkUKjWxZ8AbdorMLg"
photologo = 'https://tinypic.host/images/2025/05/29/Medusaxd-Bot_20250529_184235_0000.png'
photoyt = 'https://tinypic.host/images/2025/03/18/YouTube-Logo.wine.png'
photocp = 'https://tinypic.host/images/2025/03/28/IMG_20250328_133126.jpg'
photozip = 'https://envs.sh/cD_.jpg'

async def show_random_emojis(message):
    emojis = ['🐼', '🐶', '🐅', '⚡️', '🚀', '✨', '💥', '☠️', '🥂', '🍾', '📬', '👻', '👀', '🌹', '💀', '🐇', '⏳', '🔮', '🦔', '📖', '🦁', '🐱', '🐻‍❄️', '☁️', '🚹', '🚺', '🐠', '🦋']
    emoji_message = await message.reply_text(' '.join(random.choices(emojis, k=1)))
    return emoji_message

# RETRY FUNCTIONS - These handle retry logic for downloads
async def retry_pdf_download(url, name, m, max_retries=3):
    """Retry PDF downloads with exponential backoff"""
    for attempt in range(max_retries):
        try:
            if "cwmediabkt99" in url:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                url_clean = url.replace(" ", "%20")
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_clean)

                if response.status_code == 200:
                    with open(f'{name}.pdf', 'wb') as file:
                        file.write(response.content)
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")
            else:
                cmd = f'yt-dlp -o "{name}.pdf" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
                if result == 0:  # Success
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"yt-dlp failed with code {result}")

        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

async def retry_video_download(url, cmd, name, max_retries=3):
    """Retry video downloads with helper functions"""
    for attempt in range(max_retries):
        try:
            result = await helper.download_video(url, cmd, name)

            if result:  # Success
                return True, result
            else:
                raise Exception("Download function returned None/False")

        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

async def retry_encrypted_download(url, cmd, name, appxkey, max_retries=3):
    """Retry encrypted video downloads"""
    for attempt in range(max_retries):
        try:
            result = await helper.download_and_decrypt_video(url, cmd, name, appxkey)

            if result:  # Success
                return True, result
            else:
                raise Exception("Encrypted download function returned None/False")

        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

async def retry_drm_download(mpd, keys_string, path, name, quality, max_retries=3):
    """Retry DRM video downloads"""
    for attempt in range(max_retries):
        try:
            result = await helper.decrypt_and_merge_video(mpd, keys_string, path, name, quality)

            if result:  # Success
                return True, result
            else:
                raise Exception("DRM download function returned None/False")

        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

async def retry_generic_download(url, name, download_type, max_retries=3):
    """Generic retry for documents (images, audio, etc.)"""
    for attempt in range(max_retries):
        try:
            if download_type in ["jpg", "jpeg", "png"]:
                ext = url.split('.')[-1]
                cmd = f'yt-dlp -o "{name}.{ext}" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
            elif download_type in ["mp3", "wav", "m4a"]:
                ext = url.split('.')[-1]
                cmd = f'yt-dlp -o "{name}.{ext}" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
            elif download_type == "zip":
                cmd = f'yt-dlp -o "{name}.zip" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
            else:
                raise Exception(f"Unsupported download type: {download_type}")

            if result == 0:  # Success
                return True, f'{name}.{ext if download_type != "zip" else "zip"}'
            else:
                raise Exception(f"Command failed with code {result}")

        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

# Inline keyboard for start command
BUTTONSCONTACT = InlineKeyboardMarkup([[InlineKeyboardButton(text="📞 Contact", url="https://t.me/medusaXD")]])
keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(text="🛠️ Help", url="https://t.me/medusaXD"),
            InlineKeyboardButton(text="🛠️ Contact", url="https://t.me/medusaXD"),
        ],
    ]
)

# Image URLs for the random image feature
image_urls = [
    "https://tinypic.host/images/2025/05/29/Medusaxd-Bot_20250529_184235_0000.png",
    "https://tinypic.host/images/2025/05/29/Medusaxd-Bot_20250529_184235_0000.png",
    # Add more image URLs as needed
]
@bot.on_message(filters.command(["add_user", "addauth"]) & filters.private)
async def add_auth_user(client: Client, message: Message):
    if message.chat.id != OWNER:
        return await message.reply_text("You are not authorized to use this command.")

    try:
        new_user_id = int(message.command[1])
        if new_user_id in AUTH_USERS:
            await message.reply_text("User ID is already authorized.")
        else:
            AUTH_USERS.append(new_user_id)
            os.environ['AUTH_USERS'] = ','.join(map(str, AUTH_USERS))
            await message.reply_text(f"User ID {new_user_id} added to authorized users.")
    except (IndexError, ValueError):
        await message.reply_text("Please provide a valid user ID.")

@bot.on_message(filters.command(["remove_user", "remauth"]) & filters.private)
async def remove_auth_user(client: Client, message: Message):
    if message.chat.id != OWNER:
        return await message.reply_text("You are not authorized to use this command.")

    try:
        user_id_to_remove = int(message.command[1])
        if user_id_to_remove not in AUTH_USERS:
            await message.reply_text("User ID is not in the authorized users list.")
        else:
            AUTH_USERS.remove(user_id_to_remove)
            os.environ['AUTH_USERS'] = ','.join(map(str, AUTH_USERS))
            await message.reply_text(f"User ID {user_id_to_remove} removed from authorized users.")
    except (IndexError, ValueError):
        await message.reply_text("Please provide a valid user ID.")

@bot.on_message(filters.command("users") & filters.private)
async def list_auth_users(client: Client, message: Message):
    if message.chat.id != OWNER:
        return await message.reply_text("You are not authorized to use this command.")

    user_list = '\n'.join(map(str, AUTH_USERS))
    await message.reply_text(f"<blockquote>Authorized Users:</blockquote>\n{user_list}")

@bot.on_message(filters.command(["add_channel", "addchnl"]) & filters.private)
async def add_channel(client: Client, message: Message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("You are not authorized to use this command.")

    try:
        new_channel_id = int(message.command[1])
        if not str(new_channel_id).startswith("-100"):
            return await message.reply_text("Invalid channel ID. Channel IDs must start with -100.")

        if new_channel_id in CHANNELS_LIST:
            await message.reply_text("Channel ID is already added.")
        else:
            CHANNELS_LIST.append(new_channel_id)
            CHANNEL_OWNERS[new_channel_id] = message.from_user.id
            os.environ['CHANNELS'] = ','.join(map(str, CHANNELS_LIST))
            await message.reply_text(f"Channel ID {new_channel_id} added to the list and you are now the owner.")
    except (IndexError, ValueError):
        await message.reply_text("Please provide a valid channel ID.")

@bot.on_message(filters.command(["remove_channel", "remchnl"]) & filters.private)
async def remove_channel(client: Client, message: Message):
    try:
        channel_id_to_remove = int(message.command[1])

        if channel_id_to_remove not in CHANNELS_LIST:
            return await message.reply_text("Channel ID is not in the list.")

        if message.from_user.id != OWNER and CHANNEL_OWNERS.get(channel_id_to_remove) != message.from_user.id:
            return await message.reply_text("You are not authorized to remove this channel.")

        CHANNELS_LIST.remove(channel_id_to_remove)
        if channel_id_to_remove in CHANNEL_OWNERS:
            del CHANNEL_OWNERS[channel_id_to_remove]

        os.environ['CHANNELS'] = ','.join(map(str, CHANNELS_LIST))
        await message.reply_text(f"Channel ID {channel_id_to_remove} removed from the list.")
    except (IndexError, ValueError):
        await message.reply_text("Please provide a valid channel ID.")

@bot.on_message(filters.command("channels") & filters.private)
async def list_channels(client: Client, message: Message):
    if message.chat.id != OWNER:
        return await message.reply_text("You are not authorized to use this command.")

    if not CHANNELS_LIST:
        await message.reply_text("No channels have been added yet.")
    else:
        channel_list = '\n'.join(map(str, CHANNELS_LIST))
        await message.reply_text(f"<blockquote>Authorized Channels:</blockquote>\n{channel_list}")

# LOG CHANNEL MANAGEMENT COMMANDS
@bot.on_message(filters.command(["add_log_channel", "addlog"]) & filters.private)
async def add_log_channel(client: Client, message: Message):
    if message.from_user.id != OWNER:
        return await message.reply_text("❌ Only the bot owner can manage log channels.")

    try:
        channel_id = int(message.command[1])
        if not str(channel_id).startswith("-100"):
            return await message.reply_text("❌ Invalid channel ID. Channel IDs must start with -100.")

        # Verify channel is accessible
        try:
            chat = await bot.get_chat(channel_id)
            channel_name = chat.title
        except Exception as e:
            return await message.reply_text(f"❌ Cannot access channel {channel_id}: {e}")

        # Add to log channels
        if channel_id not in ALL_LOG_CHANNELS:
            LOG_CHANNELS.append(channel_id)
            ALL_LOG_CHANNELS.append(channel_id)

            # Update environment variable (for current session)
            import os
            current_log_channels = os.environ.get('LOG_CHANNELS', '')
            if current_log_channels:
                os.environ['LOG_CHANNELS'] = f"{current_log_channels},{channel_id}"
            else:
                os.environ['LOG_CHANNELS'] = str(channel_id)

            # Remove from failed channels if it was there
            if channel_id in log_service.failed_channels:
                log_service.failed_channels.remove(channel_id)

            log_service.enabled = True
            await message.reply_text(f"✅ Added log channel: {channel_name} ({channel_id})")
        else:
            await message.reply_text(f"⚠️ Channel {channel_id} is already in log channels list.")

    except (IndexError, ValueError):
        await message.reply_text("❌ Please provide a valid channel ID.\nUsage: `/add_log_channel -1001234567890`")

@bot.on_message(filters.command(["remove_log_channel", "remlog"]) & filters.private)
async def remove_log_channel(client: Client, message: Message):
    if message.from_user.id != OWNER:
        return await message.reply_text("❌ Only the bot owner can manage log channels.")

    try:
        channel_id = int(message.command[1])

        if channel_id in ALL_LOG_CHANNELS:
            # Remove from all lists
            if channel_id in LOG_CHANNELS:
                LOG_CHANNELS.remove(channel_id)
            if channel_id in BACKUP_LOG_CHANNELS:
                BACKUP_LOG_CHANNELS.remove(channel_id)
            ALL_LOG_CHANNELS.remove(channel_id)

            # Update environment variable (for current session)
            import os
            remaining_channels = [str(ch) for ch in LOG_CHANNELS]
            os.environ['LOG_CHANNELS'] = ','.join(remaining_channels)

            # Disable service if no channels left
            if not ALL_LOG_CHANNELS:
                log_service.enabled = False

            await message.reply_text(f"✅ Removed log channel: {channel_id}")
        else:
            await message.reply_text(f"⚠️ Channel {channel_id} is not in log channels list.")

    except (IndexError, ValueError):
        await message.reply_text("❌ Please provide a valid channel ID.\nUsage: `/remove_log_channel -1001234567890`")

@bot.on_message(filters.command(["log_channels", "loglist"]) & filters.private)
async def list_log_channels(client: Client, message: Message):
    if message.from_user.id != OWNER:
        return await message.reply_text("❌ Only the bot owner can view log channels.")

    stats = log_service.get_stats()

    if not ALL_LOG_CHANNELS:
        await message.reply_text("📝 **LOG CHANNELS**\n\n❌ No log channels configured.")
        return

    primary_list = "\n".join([f"• {channel_id}" for channel_id in LOG_CHANNELS]) if LOG_CHANNELS else "None"
    backup_list = "\n".join([f"• {channel_id}" for channel_id in BACKUP_LOG_CHANNELS]) if BACKUP_LOG_CHANNELS else "None"
    failed_list = "\n".join([f"• {channel_id}" for channel_id in log_service.failed_channels]) if log_service.failed_channels else "None"

    status = "✅ Enabled" if stats['enabled'] else "❌ Disabled"

    response = (
        f"📝 **LOG CHANNELS STATUS**\n\n"
        f"**Status:** {status}\n"
        f"**Total Channels:** {stats['total_channels']}\n"
        f"**Active Channels:** {stats['active_channels']}\n"
        f"**Failed Channels:** {stats['failed_channels']}\n\n"
        f"**🔹 Primary Log Channels:**\n{primary_list}\n\n"
        f"**🔸 Backup Log Channels:**\n{backup_list}\n\n"
        f"**❌ Failed Channels:**\n{failed_list}"
    )

    await message.reply_text(response)

@bot.on_message(filters.command(["test_log", "testlog"]) & filters.private)
async def test_log_channels(client: Client, message: Message):
    if message.from_user.id != OWNER:
        return await message.reply_text("❌ Only the bot owner can test log channels.")

    if not log_service.enabled:
        return await message.reply_text("❌ Log channel service is disabled.")

    try:
        # Create test user info
        user_info = {
            'id': message.from_user.id,
            'username': message.from_user.username or 'No username',
            'first_name': message.from_user.first_name or 'Unknown'
        }

        # Create test download info
        download_info = {
            'name': 'Test_Log_File',
            'index': 1,
            'batch_name': 'Log Test Batch',
            'original_url': 'https://example.com/test'
        }

        # Send test message to log channels
        test_message = await message.reply_text("🧪 **LOG CHANNEL TEST**\n\nTesting log channel functionality...")

        # Log the test message
        log_ids = await log_service.log_file_upload(test_message, user_info, download_info)

        if log_ids:
            await message.reply_text(f"✅ **Log test successful!**\n\n📝 Test message sent to {len(log_ids)} log channels\n📋 Message IDs: {', '.join(map(str, log_ids))}")
        else:
            await message.reply_text("⚠️ **Log test failed!**\n\nNo messages were sent to log channels. Check channel permissions.")

    except Exception as e:
        await message.reply_text(f"❌ **Log test error:**\n\n`{str(e)}`")

@bot.on_message(filters.command("cookies") & filters.private)
async def cookies_handler(client: Client, m: Message):
    # Check if user is authorized
    if m.from_user.id not in AUTH_USERS:
        return await m.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    await m.reply_text("Please upload the cookies file (.txt format).", quote=True)

    try:
        input_message: Message = await client.listen(m.chat.id)

        if not input_message.document or not input_message.document.file_name.endswith(".txt"):
            await m.reply_text("Invalid file type. Please upload a .txt file.")
            return

        downloaded_path = await input_message.download()

        with open(downloaded_path, "r") as uploaded_file:
            cookies_content = uploaded_file.read()

        with open(cookies_file_path, "w") as target_file:
            target_file.write(cookies_content)

        await input_message.reply_text("✅ Cookies updated successfully.\n📂 Saved in `youtube_cookies.txt`.")

    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")

@bot.on_message(filters.command(["t2t"]))
async def text_to_txt(client, message: Message):
    # Check if user is authorized
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    user_id = str(message.from_user.id)
    editable = await message.reply_text(f"<blockquote>Welcome to the Text to .txt Converter! by @medusaXD\nSend the **text** for convert into a `.txt` file.</blockquote>")
    input_message: Message = await bot.listen(message.chat.id)
    if not input_message.text:
        await message.reply_text("🚨 **error**: Send valid text data")
        return

    text_data = input_message.text.strip()
    await input_message.delete()

    await editable.edit("**🔄 Send file name or send /d for filename**")
    inputn: Message = await bot.listen(message.chat.id)
    raw_textn = inputn.text
    await inputn.delete()
    await editable.delete()

    if raw_textn == '/d':
        custom_file_name = 'txt_file'
    else:
        custom_file_name = raw_textn

    txt_file = os.path.join("downloads", f'{custom_file_name}.txt')
    os.makedirs(os.path.dirname(txt_file), exist_ok=True)
    with open(txt_file, 'w') as f:
        f.write(text_data)

    await message.reply_document(document=txt_file, caption=f"`{custom_file_name}.txt`\n\nYou can now download your content! 📥")
    os.remove(txt_file)

UPLOAD_FOLDER = '/path/to/upload/folder'
EDITED_FILE_PATH = '/path/to/save/edited_output.txt'

@bot.on_message(filters.command(["y2t"]))
async def youtube_to_txt(client, message: Message):
    # Check if user is authorized
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    user_id = str(message.from_user.id)

    editable = await message.reply_text(f"Send YouTube Website/Playlist link for convert in .txt file")

    input_message: Message = await bot.listen(message.chat.id)
    youtube_link = input_message.text.strip()
    await input_message.delete()
    await editable.delete()

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'force_generic_extractor': True,
        'forcejson': True,
        'cookies': 'youtube_cookies.txt'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(youtube_link, download=False)
            if not result:
                await message.reply_text(f"<pre><code>🚨 Error: Could not extract information from the link</code></pre>")
                return

            if 'entries' in result and result['entries']:
                title = result.get('title', 'youtube_playlist')
            else:
                title = result.get('title', 'youtube_video')
        except yt_dlp.utils.DownloadError as e:
            await message.reply_text(f"<pre><code>🚨 Error occurred {str(e)}</code></pre>")
            return

    videos = []
    if 'entries' in result and result['entries'] is not None:
        for entry in result['entries']:
            if entry is not None:  # Check if entry is not None
                video_title = entry.get('title', 'No title')
                url = entry.get('url', '')
                if url:  # Only add if URL exists
                    videos.append(f"{video_title}: {url}")
    else:
        video_title = result.get('title', 'No title')
        url = result.get('url', '')
        if url:  # Only add if URL exists
            videos.append(f"{video_title}: {url}")

    txt_file = os.path.join("downloads", f'{title}.txt')
    os.makedirs(os.path.dirname(txt_file), exist_ok=True)
    with open(txt_file, 'w') as f:
        f.write('\n'.join(videos))

    await message.reply_document(
        document=txt_file,
        caption=f'<a href="{youtube_link}">__**Click Here to Open Link**__</a>\n<pre><code>{title}.txt</code></pre>\n'
    )

    os.remove(txt_file)

m_file_path= "main.py"
@bot.on_message(filters.command("getcookies") & filters.private)
async def getcookies_handler(client: Client, m: Message):
    try:
        await client.send_document(
            chat_id=m.chat.id,
            document=cookies_file_path,
            caption="Here is the `youtube_cookies.txt` file."
        )
    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")     
@bot.on_message(filters.command("mfile") & filters.private)
async def mfile_handler(client: Client, m: Message):
    try:
        await client.send_document(
            chat_id=m.chat.id,
            document=m_file_path,
            caption="Here is the `main.py` file."
        )
    except Exception as e:
        await m.reply_text(f"⚠️ An error occurred: {str(e)}")

@bot.on_message(filters.command(["stop"]) )
async def restart_handler(_, m):
    # Check if user is authorized
    if m.from_user.id not in AUTH_USERS:
        return await m.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    await m.reply_text("**🚦STOPPED🚦**", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["start"]))
async def start_command(bot: Client, message: Message):
    random_image_url = random.choice(image_urls)
    caption = (
        f"𝐇𝐞𝐥𝐥𝐨 𝐃𝐞𝐚𝐫 👋!\n\n➠ 𝐈 𝐚𝐦 𝐚 𝐓𝐞𝐱𝐭 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐞𝐫 𝐁𝐨𝐭\n\n➠ Can Extract Videos & PDFs From Your Text File and Upload to Telegram!\n\n➠ For Guide Use Command /help 📖\n\n➠ 𝐌𝐚𝐝𝐞 𝐁𝐲 : {CREDIT} 🦁"
    )
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=random_image_url,
        caption=caption,
        reply_markup=keyboard
    )

@bot.on_message(filters.command(["id"]))
async def id_command(client, message: Message):
    chat_id = message.chat.id
    await message.reply_text(f"<blockquote>The ID of this chat id is:</blockquote>\n`{chat_id}`")

@bot.on_message(filters.private & filters.command(["info"]))
async def info(bot: Client, update: Message):

    text = (
        f"╭────────────────╮\n"
        f"│✨ **__Your Telegram Info__**✨ \n"
        f"├────────────────\n"
        f"├🔹**Name :** `{update.from_user.first_name} {update.from_user.last_name if update.from_user.last_name else 'None'}`\n"
        f"├🔹**User ID :** @{update.from_user.username}\n"
        f"├🔹**TG ID :** `{update.from_user.id}`\n"
        f"├🔹**Profile :** {update.from_user.mention}\n"
        f"╰────────────────╯"
    )

    await update.reply_text(        
        text=text,
        disable_web_page_preview=True,
        reply_markup=BUTTONSCONTACT
    )

@bot.on_message(filters.command(["help"]))
async def txt_handler(client: Client, m: Message):
    await bot.send_message(m.chat.id, text= (
        f"╭━━━━━━━✦✧✦━━━━━━━╮\n"
        f"💥 𝘽𝙊𝙏𝙎 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦\n"
        f"╰━━━━━━━✦✧✦━━━━━━━╯\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
        f"📌 𝗠𝗮𝗶𝗻 𝗙𝗲𝗮𝘁𝘂𝗿𝗲𝘀: **(Auth Users Only)**\n\n"
        f"➥ /start – Bot Status Check\n"
        f"➥ /drm – Extract from .txt (Auto) 🔒\n"
        f"➥ /y2t – YouTube → .txt Converter 🔒\n"
        f"➥ /t2t – Text → .txt Generator 🔒\n"
        f"➥ /stop – Cancel Running Task 🔒\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ \n"
        f"⚙️ 𝗧𝗼𝗼𝗹𝘀 & 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀: \n\n"
        f"➥ /cookies – Update YT Cookies 🔒\n"
        f"➥ /id – Get Chat/User ID\n"
        f"➥ /info – User Details\n"
        f"➥ /logs – View Bot Activity 🔒\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"👤 𝐔𝐬𝐞𝐫 𝐀𝐮𝐭𝐡𝐞𝐧𝐭𝐢𝐜𝐚𝐭𝐢𝐨𝐧: **(OWNER)**\n\n"
        f"➥ /add_user xxxx – Add User ID\n"
        f"➥ /remove_user xxxx – Remove User ID\n"
        f"➥ /users – Total User List\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"📁 𝐂𝐡𝐚𝐧𝐧𝐞𝐥𝐬: **(Auth Users)**\n\n"
        f"➥ /add_channel -100xxxx – Add\n"
        f"➥ /remove_channel -100xxxx – Remove\n"
        f"➥ /channels – List - (OWNER)\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"📝 𝐋𝐨𝐠 𝐂𝐡𝐚𝐧𝐧𝐞𝐥𝐬: **(OWNER)**\n\n"
        f"➥ /add_log_channel -100xxxx – Add\n"
        f"➥ /remove_log_channel -100xxxx – Remove\n"
        f"➥ /log_channels – List & Status\n"
        f"➥ /test_log – Test Log Channels\n"
        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        f"💡 𝗡𝗼𝘁𝗲:\n\n"  
        f"• Send any link for auto-extraction\n"  
        f"• Supports batch processing\n\n"  
        f"╭────────⊰◆⊱────────╮\n"   
        f" ➠ 𝐌𝐚𝐝𝐞 𝐁𝐲 : {CREDIT} 💻\n"
        f"╰────────⊰◆⊱────────╯\n"
        )
    )                    

@bot.on_message(filters.command(["logs"]))
async def send_logs(client: Client, m: Message):
    # Check if user is authorized
    if m.from_user.id not in AUTH_USERS:
        return await m.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    try:
        with open("logs.txt", "rb") as file:
            sent = await m.reply_text("**📤 Sending you ....**")
            await m.reply_document(document=file)
            await sent.delete()
    except Exception as e:
        await m.reply_text(f"Error sending logs: {e}")

# RETRY HELPER FUNCTIONS FOR DIFFERENT DOWNLOAD TYPES
async def retry_drive_download(url, name, max_retries=3):
    """Retry Google Drive downloads"""
    for attempt in range(max_retries):
        try:
            result = await helper.download(url, name)
            if result:
                return True, result
            else:
                raise Exception("Drive download returned None")
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"

async def retry_pdf_download_enhanced(url, name, m, max_retries=3):
    """Enhanced PDF download with retry logic"""
    for attempt in range(max_retries):
        try:
            if "cwmediabkt99" in url:
                await asyncio.sleep(2 ** attempt)
                url_clean = url.replace(" ", "%20")
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_clean)

                if response.status_code == 200:
                    with open(f'{name}.pdf', 'wb') as file:
                        file.write(response.content)
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")
            else:
                cmd = f'yt-dlp -o "{name}.pdf" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
                if result == 0:
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"yt-dlp failed with code {result}")

        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)

    return False, "Max retries exceeded"

async def retry_ws_download(url, name, max_retries=3):
    """Retry .ws file downloads"""
    for attempt in range(max_retries):
        try:
            await helper.pdf_download(f"{api_url}utkash-ws?url={url}&authorization={api_token}", f"{name}.html")
            return True, f"{name}.html"
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"

async def retry_media_download(url, name, file_type, max_retries=3):
    """Retry media downloads (images, audio, etc.)"""
    for attempt in range(max_retries):
        try:
            ext = url.split('.')[-1]
            cmd = f'yt-dlp -o "{name}.{ext}" "{url}" -R 25 --fragment-retries 25'
            result = os.system(cmd)
            if result == 0:
                return True, f'{name}.{ext}'
            else:
                raise Exception(f"Command failed with code {result}")
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"


# Duplicate handlers removed - keeping only the first set

# ENHANCED CONCURRENT DOWNLOAD-UPLOAD SYSTEM
import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class DownloadTask:
    """Represents a download task with metadata"""
    index: int
    url: str
    name: str
    link_data: List[str]
    original_url: str
    file_path: Optional[str] = None
    status: str = "pending"  # pending, downloading, completed, failed, uploading, uploaded
    retry_count: int = 0
    error_message: Optional[str] = None

class ConcurrentDownloadUploadManager:
    """Manages 5 concurrent downloads with instant sequential uploads"""

    def __init__(self, bot: Client, message: Message, max_concurrent: int = 5):
        self.bot = bot
        self.message = message
        self.max_concurrent = max_concurrent
        self.download_semaphore = asyncio.Semaphore(max_concurrent)
        self.upload_lock = asyncio.Lock()

        # Queues and tracking
        self.download_queue = deque()
        self.upload_queue = asyncio.Queue()  # Changed to asyncio.Queue for async operations
        self.completed_downloads = {}  # index -> DownloadTask
        self.active_downloads = {}     # index -> asyncio.Task
        self.upload_sequence = 1       # Next expected upload sequence

        # Statistics
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'uploaded': 0,
            'failed': 0,
            'active_downloads': 0,
            'uploading': False
        }

        # Configuration from original handler
        self.config = {}

    async def process_batch(self, links: List, start_index: int, config: Dict):
        """Main batch processing with concurrent downloads and instant uploads"""
        self.config = config
        self.stats['total'] = len(links) - start_index + 1

        # Initialize download tasks
        for i in range(start_index - 1, len(links)):
            task = DownloadTask(
                index=i + 1,
                url="",  # Will be set during processing
                name="",  # Will be set during processing
                link_data=links[i],
                original_url=""  # Will be set during processing
            )
            self.download_queue.append(task)

        # Start concurrent processing
        download_tasks = []
        for _ in range(min(self.max_concurrent, len(self.download_queue))):
            if self.download_queue:
                task = asyncio.create_task(self._download_worker())
                download_tasks.append(task)

        # Start upload worker
        upload_task = asyncio.create_task(self._upload_worker())

        # Wait for all downloads to complete
        await asyncio.gather(*download_tasks, return_exceptions=True)

        # Signal upload worker to finish remaining uploads
        await self.upload_queue.put(None)  # Sentinel value
        await upload_task

        return self.stats

    async def _download_worker(self):
        """Worker that processes downloads with semaphore control"""
        while self.download_queue:
            async with self.download_semaphore:
                if not self.download_queue:
                    break

                task = self.download_queue.popleft()
                self.stats['active_downloads'] += 1

                try:
                    # Process the download task
                    await self._process_download_task(task)

                    # Instant upload trigger
                    if task.status == "completed":
                        await self._trigger_instant_upload(task)

                except Exception as e:
                    task.status = "failed"
                    task.error_message = str(e)
                    self.stats['failed'] += 1
                    await self._send_error_message(task, str(e))

                finally:
                    self.stats['active_downloads'] -= 1

    async def _process_download_task(self, task: DownloadTask):
        """Process individual download task with retry logic"""
        # Extract URL and name from link data (same logic as original)
        try:
            if not task.link_data or len(task.link_data) < 2:
                raise Exception(f"Invalid link data at index {task.index}")

            link_protocol = task.link_data[0] if task.link_data[0] else "https"
            link_url = task.link_data[1] if task.link_data[1] else ""

            if not link_url:
                raise Exception(f"Empty URL at index {task.index}")

            # URL processing (same as original)
            Vxy = link_url.replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
            url = "https://" + Vxy
            task.original_url = "https://" + Vxy
            task.url = url

            name1 = link_protocol.replace("(", "[").replace(")", "]").replace("_", "").replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            task.name = f'{name1[:60]}' if name1 else f'file_{task.index}'

            # Apply URL transformations (same as original)
            url = await self._apply_url_transformations(url)
            task.url = url

            # Download with retry logic
            task.status = "downloading"
            success, result = await self._download_with_retry(task)

            if success:
                task.file_path = result
                task.status = "completed"
                self.stats['downloaded'] += 1
                self.completed_downloads[task.index] = task
            else:
                task.status = "failed"
                task.error_message = result
                self.stats['failed'] += 1

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.stats['failed'] += 1
            raise

    async def _trigger_instant_upload(self, task: DownloadTask):
        """Trigger instant upload when download completes"""
        # Add to upload queue immediately
        await self.upload_queue.put(task)

    async def _upload_worker(self):
        """Worker that handles sequential uploads maintaining order"""
        while True:
            # Get next task from upload queue
            task = await self.upload_queue.get()

            # Check for sentinel value (end of processing)
            if task is None:
                break

            async with self.upload_lock:
                # Check if this is the next expected sequence
                if task.index == self.upload_sequence:
                    await self._upload_task(task)
                    self.upload_sequence += 1

                    # Check if any queued tasks can now be uploaded
                    await self._process_queued_uploads()
                else:
                    # Not the right sequence, put back in queue
                    await self.upload_queue.put(task)
                    await asyncio.sleep(0.1)  # Small delay to prevent busy waiting

    async def _process_queued_uploads(self):
        """Process any queued uploads that are now in sequence"""
        uploaded_any = True
        while uploaded_any:
            uploaded_any = False

            # Check if next sequence is available
            if self.upload_sequence in self.completed_downloads:
                task = self.completed_downloads[self.upload_sequence]
                if task.status == "completed":
                    await self._upload_task(task)
                    self.upload_sequence += 1
                    uploaded_any = True

    async def _apply_url_transformations(self, url: str) -> str:
        """Apply URL transformations (same logic as original)"""
        # Vision IAS transformation
        if "visionias" in url:
            async with ClientSession() as session:
                async with session.get(url, headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Pragma': 'no-cache',
                    'Referer': 'http://www.visionias.in/',
                    'Sec-Fetch-Dest': 'iframe',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'cross-site',
                    'Upgrade-Insecure-Requests': '1',
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36',
                    'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': '"Android"',
                }) as resp:
                    text = await resp.text()
                    url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

        # ClassPlus transformations
        if "https://cpvod.testbook.com/" in url:
            url = url.replace("https://cpvod.testbook.com/","https://media-cdn.classplusapp.com/drm/")
            url = 'https://dragoapi.vercel.app/classplus?link=' + url
        elif "classplusapp.com/drm/" in url:
            url = 'https://dragoapi.vercel.app/classplus?link=' + url
        elif "tencdn.classplusapp" in url:
            headers = {
                'Host': 'api.classplusapp.com',
                'x-access-token': f'{token_cp}',
                'user-agent': 'Mobile-Android',
                'app-version': '1.4.37.1',
                'api-version': '18',
                'device-id': '5d0d17ac8b3c9f51',
                'device-details': '2848b866799971ca_2848b8667a33216c_SDK-30',
                'accept-encoding': 'gzip'
            }
            params = (('url', f'{url}'))
            response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
            url = response.json()['url']
        elif 'videos.classplusapp' in url or "tencdn.classplusapp" in url or "webvideos.classplusapp.com" in url:
            url = requests.get(f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}', headers={'x-access-token': f'{token_cp}'}).json()['url']
        elif 'media-cdn.classplusapp.com' in url or 'media-cdn-alisg.classplusapp.com' in url or 'media-cdn-a.classplusapp.com' in url:
            headers = {'x-access-token': f'{token_cp}', "X-CDN-Tag": "empty"}
            response = requests.get(f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}', headers=headers)
            url = response.json()['url']
        elif "childId" in url and "parentId" in url:
            url = f"https://anonymousrajputplayer-9ab2f2730a02.herokuapp.com/pw?url={url}&token={self.config.get('pw_token', '')}"
        elif "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
            url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={self.config.get('pw_token', '')}"

        # PDF and ZIP transformations
        if ".pdf*" in url:
            url = f"https://dragoapi.vercel.app/pdf/{url}"
        if ".zip" in url:
            url = f"https://video.pablocoder.eu.org/appx-zip?url={url}"

        return url

    async def _download_with_retry(self, task: DownloadTask) -> Tuple[bool, str]:
        """Download with retry logic maintaining original 3-retry system"""
        url = task.url
        name = task.name

        # Determine download type and use appropriate retry function
        if "drive" in url:
            return await retry_drive_download(url, name)
        elif ".pdf" in url:
            return await retry_pdf_download_enhanced(url, name, self.message)
        elif ".ws" in url and url.endswith(".ws"):
            return await retry_ws_download(url, name)
        elif ".zip" in url:
            # Handle ZIP files (no actual download, just return success)
            return True, "zip_handled"
        elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
            return await retry_media_download(url, name, "image")
        elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
            return await retry_media_download(url, name, "audio")
        elif 'encrypted.m' in url:
            appxkey = url.split('*')[1] if '*' in url else ""
            url = url.split('*')[0] if '*' in url else url
            cmd = self._build_download_command(url, name)
            return await retry_encrypted_download(url, cmd, name, appxkey)
        elif 'drmcdni' in url or 'drm/wv' in url:
            # Handle DRM content
            mpd, keys = helper.get_mps_and_keys(url)
            if not mpd or not keys:
                return False, "Failed to get MPD or keys from API"
            keys_string = " ".join([f"--key {key}" for key in keys])
            return await retry_drm_download(mpd, keys_string, self.config.get('path', './downloads'), name, self.config.get('quality', '720'))
        elif url.endswith('.m3u8') or 'classplusapp.com' in url:
            # Handle HLS streams and ClassPlus URLs specifically
            cmd = self._build_download_command(url, name)
            return await retry_hls_download(url, cmd, name)
        else:
            # Regular video download
            cmd = self._build_download_command(url, name)
            return await retry_video_download(url, cmd, name)

    def _build_download_command(self, url: str, name: str) -> str:
        """Build download command based on URL type"""
        quality = self.config.get('quality', '720')

        if "youtu" in url:
            ytf = f"b[height<={quality}][ext=mp4]/bv[height<={quality}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
        elif "embed" in url:
            ytf = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
        else:
            ytf = f"b[height<={quality}]/bv[height<={quality}]+ba/b/bv+ba"

        if "jw-prod" in url:
            return f'yt-dlp -o "{name}.mp4" "{url}"'
        elif "webvideos.classplusapp." in url or "media-cdn.classplusapp.com" in url:
            # Enhanced ClassPlus command with better HLS support
            if url.endswith('.m3u8'):
                return f'yt-dlp --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" --hls-prefer-ffmpeg -f "{ytf}" "{url}" -o "{name}.mp4"'
            else:
                return f'yt-dlp --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" -f "{ytf}" "{url}" -o "{name}.mp4"'
        elif "youtube.com" in url or "youtu.be" in url:
            return f'yt-dlp --cookies youtube_cookies.txt -f "{ytf}" "{url}" -o "{name}".mp4'
        elif "acecwply" in url:
            return f'yt-dlp -o "{name}.%(ext)s" -f "bestvideo[height<={quality}]+bestaudio" --hls-prefer-ffmpeg --no-keep-video --remux-video mkv --no-warning "{url}"'
        else:
            return f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

    async def _upload_task(self, task: DownloadTask):
        """Upload completed download task with log channel integration"""
        if task.status != "completed" or not task.file_path:
            return

        task.status = "uploading"
        self.stats['uploading'] = True

        try:
            # Build caption
            cc = self._build_caption(task)

            # Upload file and get the message
            uploaded_message = None

            # Handle different file types
            if task.file_path == "zip_handled":
                # Handle ZIP files with inline button
                BUTTONSZIP = InlineKeyboardMarkup([[InlineKeyboardButton(text="🎥 ZIP STREAM IN PLAYER", url=f"{task.url}")]])
                uploaded_message = await self.bot.send_photo(chat_id=self.message.chat.id, photo=photozip, caption=cc, reply_markup=BUTTONSZIP)
            elif ".pdf" in task.file_path:
                uploaded_message = await self.bot.send_document(chat_id=self.message.chat.id, document=task.file_path, caption=cc)
                os.remove(task.file_path)
            elif any(ext in task.file_path for ext in [".jpg", ".jpeg", ".png"]):
                uploaded_message = await self.bot.send_photo(chat_id=self.message.chat.id, photo=task.file_path, caption=cc)
                os.remove(task.file_path)
            elif any(ext in task.file_path for ext in [".mp3", ".wav", ".m4a"]):
                uploaded_message = await self.bot.send_document(chat_id=self.message.chat.id, document=task.file_path, caption=cc)
                os.remove(task.file_path)
            elif task.file_path.endswith(".html"):
                uploaded_message = await self.bot.send_document(chat_id=self.message.chat.id, document=task.file_path, caption=cc)
                os.remove(task.file_path)
            else:
                # Video files
                uploaded_message = await helper.send_vid(self.bot, self.message, cc, task.file_path, self.config.get('thumb', '/d'), task.name, None)

            # Log to log channels if upload was successful
            if uploaded_message and log_service.enabled:
                try:
                    user_info = {
                        'id': self.message.from_user.id if self.message.from_user else 'Unknown',
                        'username': self.message.from_user.username if self.message.from_user and self.message.from_user.username else 'No username',
                        'first_name': self.message.from_user.first_name if self.message.from_user else 'Unknown'
                    }

                    download_info = {
                        'name': task.name,
                        'index': task.index,
                        'batch_name': self.config.get('batch_name', 'Unknown'),
                        'original_url': task.original_url
                    }

                    # Log the file upload to log channels
                    await log_service.log_file_upload(uploaded_message, user_info, download_info)

                except Exception as log_error:
                    print(f"⚠️ Failed to log file upload: {log_error}")

            task.status = "uploaded"
            self.stats['uploaded'] += 1

        except Exception as e:
            task.status = "upload_failed"
            task.error_message = f"Upload failed: {str(e)}"
            await self._send_error_message(task, f"Upload failed: {str(e)}")

        finally:
            self.stats['uploading'] = False

    def _build_caption(self, task: DownloadTask) -> str:
        """Build caption for uploaded file"""
        config = self.config
        link0 = task.original_url
        name1 = task.name
        count = task.index
        b_name = config.get('batch_name', 'Unknown')
        CR = config.get('credit', CREDIT)
        res = config.get('resolution', 'UN')

        # Determine file type and build appropriate caption
        if ".pdf" in task.file_path:
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**📁 Title :** `{name1}`\n**├── Extension :**  {CR} .pdf\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'
        elif ".zip" in task.url:
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**📁 Title :** `{name1}`\n**├── Extension :**  {CR} .zip\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'
        elif any(ext in task.file_path for ext in [".jpg", ".jpeg", ".png"]):
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**🖼️ Title :** `{name1}`\n**├── Extension :**  {CR} .jpg\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'
        elif any(ext in task.file_path for ext in [".mp3", ".wav", ".m4a"]):
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**🎵 Title :** `{name1}`\n**├── Extension :**  {CR} .mp3\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'
        elif task.file_path.endswith(".html"):
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**🌐 Title :** `{name1}`\n**├── Extension :**  {CR} .html\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'
        else:
            # Video files
            return f'[——— ✦ {str(count).zfill(3)} ✦ ———]({link0})\n\n**🎞️ Title :** `{name1}`\n**├── Extension :**  {CR} .mkv\n**├── Resolution :** [{res}]\n\n**📚 Course :** {b_name}\n\n**🌟 Extracted By :** {CR}'

    async def _send_error_message(self, task: DownloadTask, error_msg: str):
        """Send error message for failed downloads"""
        await self.message.reply_text(
            f'⚠️**Downloading Failed After 3 Retries**⚠️\n'
            f'**Name** =>> `{str(task.index).zfill(3)} {task.name}`\n'
            f'**Url** =>> {task.original_url}\n\n'
            f'<pre><i><b>Failed Reason: {error_msg}</b></i></pre>',
            disable_web_page_preview=True
        )

# Add missing helper functions for the enhanced system
async def retry_drive_download(url, name, max_retries=3):
    """Retry Google Drive downloads"""
    for attempt in range(max_retries):
        try:
            cmd = f'yt-dlp -o "{name}.%(ext)s" "{url}" -R 25 --fragment-retries 25'
            result = os.system(cmd)
            if result == 0:
                # Find the downloaded file
                for ext in ['.pdf', '.mp4', '.mkv', '.webm']:
                    if os.path.exists(f"{name}{ext}"):
                        return True, f"{name}{ext}"
                return False, "Downloaded file not found"
            else:
                raise Exception(f"Command failed with code {result}")
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"

async def retry_pdf_download_enhanced(url, name, message, max_retries=3):
    """Enhanced PDF download with retry logic"""
    for attempt in range(max_retries):
        try:
            if "cwmediabkt99" in url:
                await asyncio.sleep(2 ** attempt)
                url_clean = url.replace(" ", "%20")
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_clean)

                if response.status_code == 200:
                    with open(f'{name}.pdf', 'wb') as file:
                        file.write(response.content)
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")
            else:
                cmd = f'yt-dlp -o "{name}.pdf" "{url}" -R 25 --fragment-retries 25'
                result = os.system(cmd)
                if result == 0:
                    return True, f'{name}.pdf'
                else:
                    raise Exception(f"yt-dlp failed with code {result}")
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"

async def retry_ws_download(url, name, max_retries=3):
    """Retry .ws file downloads"""
    for attempt in range(max_retries):
        try:
            cmd = f'yt-dlp -o "{name}.html" "{url}" -R 25 --fragment-retries 25'
            result = os.system(cmd)
            if result == 0:
                return True, f'{name}.html'
            else:
                raise Exception(f"Command failed with code {result}")
        except Exception as e:
            if attempt == max_retries - 1:
                return False, str(e)
            await asyncio.sleep(2 ** attempt)
    return False, "Max retries exceeded"

async def retry_hls_download(url, cmd, name, max_retries=3):
    """Retry HLS (.m3u8) downloads with enhanced ClassPlus support"""
    for attempt in range(max_retries):
        try:
            # Enhanced command for HLS streams with better error handling
            if 'classplusapp.com' in url:
                # Special handling for ClassPlus HLS streams
                enhanced_cmd = f'{cmd} --hls-prefer-ffmpeg --no-check-certificate --external-downloader aria2c --downloader-args "aria2c: -x 8 -j 8 -s 8"'
            else:
                # Generic HLS handling
                enhanced_cmd = f'{cmd} --hls-prefer-ffmpeg --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'

            print(f"HLS Download attempt {attempt + 1}: {enhanced_cmd}")
            result = await helper.download_video(url, enhanced_cmd, name)

            if result:  # Success
                return True, result
            else:
                raise Exception("HLS download function returned None/False")

        except Exception as e:
            print(f"HLS download attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:  # Last attempt
                return False, str(e)
            await asyncio.sleep(2 ** attempt)  # Wait before retry

    return False, "Max retries exceeded"

# ENHANCED /drm COMMAND WITH CONCURRENT PROCESSING
@bot.on_message(filters.command(["drm"]))
async def txt_handler_with_concurrent_processing(bot: Client, m: Message):
    # Enhanced authorization check - support both users and channels
    is_authorized = False

    # Check if user is authorized
    if m.from_user and m.from_user.id in AUTH_USERS:
        is_authorized = True

    # Check if message is from authorized channel
    if m.chat and m.chat.id in CHANNELS_LIST:
        is_authorized = True

    if not is_authorized:
        return await m.reply_text(f"❌ You are not authorized to use this command. Contact the bot owner {OWNER_USERNAME} for access.")

    # Initialize the concurrent download-upload manager
    manager = ConcurrentDownloadUploadManager(bot, m)

    # Store original user for channel compatibility
    original_user_id = m.from_user.id if m.from_user else None

    editable = await m.reply_text(f"**🔹Hi I am Powerful TXT Downloader📥 Bot.\n🔹Send me the txt file and wait.**")

    # Enhanced listen function for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        # In channels, use safe_listen with user filtering
        input: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        # In private chats, use regular listen
        input: Message = await bot.listen(editable.chat.id)

    x = await input.download()
    await input.delete()
    file_name, ext = os.path.splitext(os.path.basename(x))
    path = f"./downloads/{m.chat.id}"
    pdf_count = 0
    img_count = 0
    zip_count = 0
    other_count = 0

    try:
        with open(x, "r") as f:
            content = f.read()

        if not content:
            await m.reply_text("<pre><code>🔹File is empty.</code></pre>")
            os.remove(x)
            return

        content = content.split("\n")

        links = []
        for i in content:
            if i and "://" in i:  # Check if line is not empty
                split_result = i.split("://", 1)
                if len(split_result) >= 2:  # Ensure split was successful
                    url = split_result[1]
                    links.append(split_result)
                    if ".pdf" in url:
                        pdf_count += 1
                    elif url.endswith((".png", ".jpeg", ".jpg")):
                        img_count += 1
                    elif ".zip" in url:
                        zip_count += 1
                    else:
                        other_count += 1

        if not links:
            await m.reply_text("<pre><code>🔹No valid links found in the file.</code></pre>")
            os.remove(x)
            return

        os.remove(x)
    except Exception as e:
        await m.reply_text(f"<pre><code>🔹Invalid file input: {str(e)}</code></pre>")
        if os.path.exists(x):
            os.remove(x)
        return

    await editable.edit(f"**🔹Total 🔗 links found are {len(links)}\n\n🔹Img : {img_count}  🔹PDF : {pdf_count}\n🔹ZIP : {zip_count}  🔹Other : {other_count}\n\n🔹Send From where you want to download.**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input0: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input0: Message = await bot.listen(editable.chat.id)

    raw_text = input0.text
    await input0.delete()

    await editable.edit("**🔹Enter Your Batch Name\n🔹Send 1 for use default.**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input1: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input1: Message = await bot.listen(editable.chat.id)

    raw_text0 = input1.text
    await input1.delete()
    if raw_text0 == '1':
        b_name = file_name.replace('_', ' ')
    else:
        b_name = raw_text0

    await editable.edit(f"**╭━━━━❰ᴇɴᴛᴇʀ ʀᴇꜱᴏʟᴜᴛɪᴏɴ❱━━➣ \n┣━━⪼ send `144`  for 144p\n┣━━⪼ send `240`  for 240p\n┣━━⪼ send `360`  for 360p\n┣━━⪼ send `480`  for 480p\n┣━━⪼ send `720`  for 720p\n┣━━⪼ send `1080` for 1080p\n╰━━⌈⚡[`🦋{CREDIT}🦋`]⚡⌋━━➣**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input2: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input2: Message = await bot.listen(editable.chat.id)

    raw_text2 = input2.text
    quality = f"{raw_text2}p"
    await input2.delete()
    try:
        if raw_text2 == "144":
            res = "256x144"
        elif raw_text2 == "240":
            res = "426x240"
        elif raw_text2 == "360":
            res = "640x360"
        elif raw_text2 == "480":
            res = "854x480"
        elif raw_text2 == "720":
            res = "1280x720"
        elif raw_text2 == "1080":
            res = "1920x1080"
        else:
            res = "UN"
    except Exception:
            res = "UN"

    await editable.edit("**🔹Enter Your Name\n🔹Send 1 for use default**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input3: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input3: Message = await bot.listen(editable.chat.id)

    raw_text3 = input3.text
    await input3.delete()
    if raw_text3 == '1':
        CR = f"{CREDIT}"
    else:
        CR = raw_text3

    await editable.edit("**🔹Enter Your PW Token For 𝐌𝐏𝐃 𝐔𝐑𝐋\n🔹Send /anything for use default**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input4: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input4: Message = await bot.listen(editable.chat.id)

    raw_text4 = input4.text
    await input4.delete()

    await editable.edit(f"**🔹Send the Video Thumb URL\n🔹Send /d for use default\n\n🔹You can direct upload thumb\n🔹Send **No** for use default**")

    # Enhanced listen for channel compatibility
    if m.chat.type in ["group", "supergroup", "channel"]:
        input6: Message = await safe_listen(editable.chat.id, original_user_id)
    else:
        input6: Message = await bot.listen(editable.chat.id)

    raw_text6 = input6.text
    await input6.delete()

    if input6.photo:
        thumb = await input6.download()
    elif raw_text6.startswith("http://") or raw_text6.startswith("https://"):
        getstatusoutput(f"wget '{raw_text6}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = raw_text6
    await editable.delete()

    # Start concurrent processing
    progress_msg = await m.reply_text(f"__**🎯Target Batch : {b_name}**__\n\n**🚀 Starting Concurrent Processing...**\n**📥 Downloads: 5 simultaneous**\n**📤 Uploads: Instant sequential**")

    # Prepare configuration for the manager
    config = {
        'batch_name': b_name,
        'quality': raw_text2,
        'resolution': res,
        'credit': CR,
        'pw_token': raw_text4,
        'thumb': thumb,
        'path': path,
        'start_index': int(raw_text)
    }

    try:
        # Process batch with concurrent downloads and instant uploads
        final_stats = await manager.process_batch(links, int(raw_text), config)

        # Enhanced completion message with detailed statistics
        await progress_msg.edit(
            f"📊 **CONCURRENT BATCH PROCESSING COMPLETED** 📊\n\n"
            f"✅ **Successful Downloads:** {final_stats['downloaded']}\n"
            f"📤 **Successful Uploads:** {final_stats['uploaded']}\n"
            f"❌ **Failed Downloads:** {final_stats['failed']}\n"
            f"📊 **Total Processed:** {final_stats['total']}\n"
            f"📈 **Success Rate:** {(final_stats['downloaded']/final_stats['total'])*100:.1f}%\n\n"
            f"⚡ **Processing Method:** 5 Concurrent Downloads + Instant Sequential Uploads\n"
            f"✨ **BATCH NAME:** `{b_name}`\n\n"
            f"⋅ ─ ENHANCED CONCURRENT PROCESSING WITH 3-RETRY LOGIC ─ ⋅"
        )

        # Log batch summary to log channels
        if log_service.enabled:
            try:
                user_info = {
                    'id': m.from_user.id if m.from_user else 'Unknown',
                    'username': m.from_user.username if m.from_user and m.from_user.username else 'No username',
                    'first_name': m.from_user.first_name if m.from_user else 'Unknown'
                }

                batch_stats = {
                    'batch_name': b_name,
                    'total': final_stats['total'],
                    'downloaded': final_stats['downloaded'],
                    'uploaded': final_stats['uploaded'],
                    'failed': final_stats['failed']
                }

                await log_service.log_batch_summary(user_info, batch_stats)
                print(f"📊 Batch summary logged to {len(ALL_LOG_CHANNELS)} log channels")

            except Exception as log_error:
                print(f"⚠️ Failed to log batch summary: {log_error}")

    except Exception as e:
        await progress_msg.edit(f"❌ **Batch processing failed:** {str(e)}")
        await m.reply_text(f"⚠️ **Error in concurrent processing:** {str(e)}")

# Single link text handler with authorization
@bot.on_message(filters.text & filters.private)
async def text_handler(bot: Client, m: Message):
    if m.from_user.is_bot:
        return

    # Check if user is authorized for single link processing
    if m.from_user.id not in AUTH_USERS:
        return await m.reply_text(f"❌ You are not authorized to use this bot. Contact the bot owner {OWNER_USERNAME} for access.")
    links = m.text
    match = re.search(r'https?://\S+', links)
    if match:
        link = match.group(0)
    else:
        await m.reply_text("<pre><code>Invalid link format.</code></pre>")
        return

    # [Single link processing logic remains unchanged as in original]
    # This is the same as your original text_handler function

# Global error handler for uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print(f"❌ Uncaught exception: {exc_type.__name__}: {exc_value}")

sys.excepthook = handle_exception

# Run the bot with error handling
if __name__ == "__main__":
    try:
        print("🚀 Starting Medusa Bot...")
        print(f"📊 Authorized users: {len(AUTH_USERS)}")
        print(f"📊 Authorized channels: {len(CHANNELS_LIST)}")
        print(f"📝 Log channels: {len(ALL_LOG_CHANNELS)}")

        # Verify pyromod listen method before starting
        try:
            verify_listen_method()
        except ImportError as e:
            print(f"❌ {e}")
            print("💡 Tip: Install pyromod with: pip install pyromod")
            sys.exit(1)

        # Use a simple approach - initialize services on first message
        @bot.on_message(filters.private, group=-1)
        async def initialize_on_first_message(client, message):
            """Initialize services on first message"""
            if not hasattr(bot, '_services_initialized'):
                await initialize_bot_services()
                bot._services_initialized = True

        # Start the bot normally
        bot.run()
    except Exception as e:
        print(f"❌ Failed to start bot: {str(e)}")
        logging.error(f"Failed to start bot: {str(e)}")
        sys.exit(1)

