"""
Log Channel Service - Handles copying files to log channels
"""
import asyncio
from typing import List, Optional, Dict, Any
from pyrogram import Client
from pyrogram.types import Message
from datetime import datetime
import os
from config.settings import config
from database.models import channel_manager, download_manager, DownloadStatus

class LogChannelService:
    """Service for managing log channel operations"""
    
    def __init__(self, bot: Client):
        self.bot = bot
        self.log_channels = config.get_log_channels()
        self.enabled = config.is_log_channel_enabled()
        self.failed_channels = set()  # Track failed channels
        
    async def initialize(self):
        """Initialize log channel service"""
        if not self.enabled:
            print("📝 Log channel service disabled (no log channels configured)")
            return
            
        print(f"📝 Initializing log channel service with {len(self.log_channels)} channels")
        
        # Verify log channels are accessible
        accessible_channels = []
        for channel_id in self.log_channels:
            try:
                chat = await self.bot.get_chat(channel_id)
                accessible_channels.append(channel_id)
                print(f"✅ Log channel accessible: {chat.title} ({channel_id})")
            except Exception as e:
                print(f"❌ Log channel not accessible: {channel_id} - {e}")
                self.failed_channels.add(channel_id)
        
        self.log_channels = accessible_channels
        if not self.log_channels:
            print("⚠️ No accessible log channels found, disabling log channel service")
            self.enabled = False
    
    async def log_file_upload(self, original_message: Message, user_info: Dict[str, Any], 
                             download_info: Dict[str, Any], download_id: int = None) -> List[int]:
        """
        Log file upload to all configured log channels
        
        Args:
            original_message: The original message with the file
            user_info: Information about the user who requested the download
            download_info: Information about the download (URL, platform, etc.)
            download_id: Database ID of the download record
            
        Returns:
            List of message IDs in log channels
        """
        if not self.enabled or not self.log_channels:
            return []
        
        log_message_ids = []
        
        # Create log caption
        caption = self._create_log_caption(user_info, download_info)
        
        for channel_id in self.log_channels:
            if channel_id in self.failed_channels:
                continue
                
            try:
                # Copy the file to log channel
                log_message = await self._copy_file_to_channel(
                    original_message, channel_id, caption
                )
                
                if log_message:
                    log_message_ids.append(log_message.id)
                    print(f"📝 File logged to channel {channel_id}, message ID: {log_message.id}")
                
            except Exception as e:
                print(f"❌ Failed to log file to channel {channel_id}: {e}")
                self.failed_channels.add(channel_id)
        
        # Update download record with log channel message IDs
        if download_id and log_message_ids:
            await download_manager.update_download_status(
                download_id, 
                DownloadStatus.COMPLETED,
                log_channel_message_id=log_message_ids[0]  # Store first log message ID
            )
        
        return log_message_ids
    
    async def _copy_file_to_channel(self, original_message: Message, 
                                   channel_id: int, caption: str) -> Optional[Message]:
        """Copy file from original message to log channel"""
        try:
            if original_message.video:
                return await self.bot.send_video(
                    chat_id=channel_id,
                    video=original_message.video.file_id,
                    caption=caption,
                    duration=original_message.video.duration,
                    width=original_message.video.width,
                    height=original_message.video.height,
                    thumb=original_message.video.thumbs[0].file_id if original_message.video.thumbs else None
                )
            elif original_message.document:
                return await self.bot.send_document(
                    chat_id=channel_id,
                    document=original_message.document.file_id,
                    caption=caption,
                    file_name=original_message.document.file_name
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
                print(f"⚠️ Unsupported file type for logging: {type(original_message)}")
                return None
                
        except Exception as e:
            print(f"❌ Error copying file to channel {channel_id}: {e}")
            raise
    
    def _create_log_caption(self, user_info: Dict[str, Any], 
                           download_info: Dict[str, Any]) -> str:
        """Create caption for log channel message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        caption_parts = [
            "📁 **FILE DOWNLOAD LOG**",
            "",
            f"👤 **User:** {user_info.get('name', 'Unknown')} (@{user_info.get('username', 'N/A')})",
            f"🆔 **User ID:** `{user_info.get('user_id', 'N/A')}`",
            f"🕒 **Time:** {timestamp}",
            "",
            f"🔗 **Source:** {download_info.get('platform', 'Unknown')}",
            f"📎 **Original URL:** `{download_info.get('url', 'N/A')}`",
            f"📄 **File Type:** {download_info.get('file_type', 'Unknown')}",
            f"📏 **File Size:** {download_info.get('file_size', 'Unknown')}",
        ]
        
        if download_info.get('quality'):
            caption_parts.append(f"🎬 **Quality:** {download_info['quality']}")
        
        if download_info.get('duration'):
            caption_parts.append(f"⏱️ **Duration:** {download_info['duration']}")
        
        caption_parts.extend([
            "",
            f"🤖 **Bot:** {config.config.credit}",
            f"#download #log #{download_info.get('file_type', 'file').lower()}"
        ])
        
        return "\n".join(caption_parts)
    
    async def log_batch_summary(self, user_info: Dict[str, Any], 
                               batch_stats: Dict[str, Any]) -> List[int]:
        """Log batch download summary to log channels"""
        if not self.enabled or not self.log_channels:
            return []
        
        summary_message_ids = []
        caption = self._create_batch_summary_caption(user_info, batch_stats)
        
        for channel_id in self.log_channels:
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
    
    def _create_batch_summary_caption(self, user_info: Dict[str, Any], 
                                     batch_stats: Dict[str, Any]) -> str:
        """Create caption for batch download summary"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        caption_parts = [
            "📊 **BATCH DOWNLOAD SUMMARY**",
            "",
            f"👤 **User:** {user_info.get('name', 'Unknown')} (@{user_info.get('username', 'N/A')})",
            f"🆔 **User ID:** `{user_info.get('user_id', 'N/A')}`",
            f"🕒 **Completed:** {timestamp}",
            "",
            f"📁 **Total Files:** {batch_stats.get('total_files', 0)}",
            f"✅ **Successful:** {batch_stats.get('successful', 0)}",
            f"❌ **Failed:** {batch_stats.get('failed', 0)}",
            f"📏 **Total Size:** {batch_stats.get('total_size', 'Unknown')}",
            f"⏱️ **Total Time:** {batch_stats.get('total_time', 'Unknown')}",
            "",
            "**File Types:**"
        ]
        
        # Add file type breakdown
        file_types = batch_stats.get('file_types', {})
        for file_type, count in file_types.items():
            caption_parts.append(f"  • {file_type.title()}: {count}")
        
        caption_parts.extend([
            "",
            f"🤖 **Bot:** {config.config.credit}",
            "#batch #summary #download"
        ])
        
        return "\n".join(caption_parts)
    
    async def add_log_channel(self, channel_id: int, channel_name: str = None) -> bool:
        """Add a new log channel"""
        try:
            # Verify channel is accessible
            chat = await self.bot.get_chat(channel_id)
            
            # Add to database
            success = await channel_manager.add_channel(
                channel_id, 
                config.config.owner, 
                channel_name or chat.title, 
                is_log_channel=True
            )
            
            if success:
                self.log_channels.append(channel_id)
                if channel_id in self.failed_channels:
                    self.failed_channels.remove(channel_id)
                self.enabled = True
                print(f"✅ Added log channel: {chat.title} ({channel_id})")
                return True
            
        except Exception as e:
            print(f"❌ Failed to add log channel {channel_id}: {e}")
        
        return False
    
    async def remove_log_channel(self, channel_id: int) -> bool:
        """Remove a log channel"""
        try:
            success = await channel_manager.remove_channel(channel_id)
            
            if success and channel_id in self.log_channels:
                self.log_channels.remove(channel_id)
                print(f"✅ Removed log channel: {channel_id}")
                
                # Disable service if no channels left
                if not self.log_channels:
                    self.enabled = False
                    print("📝 Log channel service disabled (no channels remaining)")
                
                return True
                
        except Exception as e:
            print(f"❌ Failed to remove log channel {channel_id}: {e}")
        
        return False
    
    async def get_log_channel_stats(self) -> Dict[str, Any]:
        """Get statistics about log channel usage"""
        return {
            "enabled": self.enabled,
            "total_channels": len(self.log_channels),
            "active_channels": len([c for c in self.log_channels if c not in self.failed_channels]),
            "failed_channels": len(self.failed_channels),
            "log_channels": self.log_channels,
            "failed_channel_ids": list(self.failed_channels)
        }
