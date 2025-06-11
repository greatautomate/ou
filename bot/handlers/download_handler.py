"""
Enhanced download handler with database integration and log channel support
"""
import os
import asyncio
from typing import Dict, Any, Optional, List
from pyrogram import Client
from pyrogram.types import Message
from datetime import datetime

from config.settings import config
from database.models import download_manager, user_manager, DownloadStatus
from bot.services.log_channel import LogChannelService
from bot.utils.helpers import (
    format_file_size, format_duration, extract_platform_from_url,
    detect_file_type, sanitize_filename, create_download_stats
)
import handler as helper

class EnhancedDownloadHandler:
    """Enhanced download handler with logging and database integration"""
    
    def __init__(self, bot: Client, log_service: LogChannelService):
        self.bot = bot
        self.log_service = log_service
        self.active_downloads = {}  # Track active downloads
        
    async def handle_single_download(self, message: Message, url: str, 
                                   quality: str = "720") -> bool:
        """Handle single file download with enhanced logging"""
        user_id = message.from_user.id
        
        # Extract information
        platform = extract_platform_from_url(url)
        file_type = detect_file_type("", url)
        
        # Create download record
        download_id = await download_manager.log_download(
            user_id=user_id,
            url=url,
            filename="",  # Will be updated later
            file_type=file_type,
            platform=platform,
            quality=quality
        )
        
        # Track download
        self.active_downloads[download_id] = {
            'user_id': user_id,
            'message': message,
            'start_time': datetime.now(),
            'url': url,
            'platform': platform
        }
        
        try:
            # Send initial status
            status_msg = await message.reply_text(
                f"🔄 **Starting Download**\n\n"
                f"**Platform:** {platform}\n"
                f"**Quality:** {quality}\n"
                f"**Status:** Initializing..."
            )
            
            # Update download status
            await download_manager.update_download_status(
                download_id, DownloadStatus.DOWNLOADING
            )
            
            # Determine download method based on URL
            success, result = await self._download_file(url, quality, status_msg)
            
            if success:
                # Upload file and log to channels
                await self._handle_successful_download(
                    message, result, download_id, platform, file_type, status_msg
                )
                return True
            else:
                # Handle failed download
                await self._handle_failed_download(
                    message, result, download_id, status_msg
                )
                return False
                
        except Exception as e:
            await self._handle_failed_download(
                message, str(e), download_id, status_msg
            )
            return False
        
        finally:
            # Remove from active downloads
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]
    
    async def handle_batch_download(self, message: Message, links: List[str], 
                                   start_index: int = 1) -> Dict[str, Any]:
        """Handle batch download with enhanced progress tracking"""
        user_id = message.from_user.id
        total_files = len(links)
        
        # Initialize batch statistics
        batch_stats = {
            'total_files': total_files,
            'successful': 0,
            'failed': 0,
            'file_types': {},
            'platforms': {},
            'total_size_bytes': 0,
            'start_time': datetime.now(),
            'downloads': []
        }
        
        # Create progress message
        progress_msg = await message.reply_text(
            f"📦 **Batch Download Started**\n\n"
            f"**Total Files:** {total_files}\n"
            f"**Starting from:** {start_index}\n"
            f"**Progress:** 0/{total_files} (0%)\n"
            f"**Status:** Initializing..."
        )
        
        # Process each link
        for i, link_data in enumerate(links[start_index-1:], start_index):
            try:
                # Extract URL and name from link data
                if isinstance(link_data, list) and len(link_data) >= 2:
                    protocol, url_part = link_data[0], link_data[1]
                    url = f"https://{url_part}"
                    name = protocol
                else:
                    url = str(link_data)
                    name = f"file_{i}"
                
                # Update progress
                await self._update_batch_progress(
                    progress_msg, i, total_files, batch_stats, f"Downloading: {name[:30]}..."
                )
                
                # Download file
                download_result = await self._process_batch_item(
                    message, url, name, i, batch_stats
                )
                
                batch_stats['downloads'].append(download_result)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error processing batch item {i}: {e}")
                batch_stats['failed'] += 1
                batch_stats['downloads'].append({
                    'index': i,
                    'url': url if 'url' in locals() else 'unknown',
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Finalize batch
        batch_stats['end_time'] = datetime.now()
        batch_stats['total_time'] = batch_stats['end_time'] - batch_stats['start_time']
        
        # Send final summary
        await self._send_batch_summary(message, batch_stats, progress_msg)
        
        # Log batch summary to log channels
        if self.log_service.enabled:
            user_info = {
                'user_id': user_id,
                'username': message.from_user.username,
                'name': f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            }
            await self.log_service.log_batch_summary(user_info, batch_stats)
        
        return batch_stats
    
    async def _download_file(self, url: str, quality: str, 
                           status_msg: Message) -> tuple[bool, str]:
        """Download file using appropriate method"""
        try:
            # Update status
            await status_msg.edit_text(
                f"🔄 **Downloading**\n\n"
                f"**URL:** {url[:50]}...\n"
                f"**Quality:** {quality}\n"
                f"**Status:** Processing..."
            )
            
            # Determine download method based on URL
            if "youtube.com" in url or "youtu.be" in url:
                return await self._download_youtube(url, quality)
            elif "classplusapp.com" in url:
                return await self._download_classplus(url, quality)
            elif "testbook.com" in url:
                return await self._download_testbook(url, quality)
            elif ".pdf" in url:
                return await self._download_pdf(url)
            elif any(ext in url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                return await self._download_video(url, quality)
            else:
                return await self._download_generic(url)
                
        except Exception as e:
            return False, str(e)
    
    async def _download_youtube(self, url: str, quality: str) -> tuple[bool, str]:
        """Download YouTube video"""
        try:
            name = f"youtube_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cmd = f'yt-dlp -f "best[height<={quality}]" -o "{name}.%(ext)s" "{url}"'
            
            result = await helper.download_video(url, cmd, name)
            if result:
                return True, result
            else:
                return False, "YouTube download failed"
                
        except Exception as e:
            return False, str(e)
    
    async def _download_classplus(self, url: str, quality: str) -> tuple[bool, str]:
        """Download ClassPlus DRM content"""
        try:
            # Use existing ClassPlus logic
            mpd, keys = helper.get_mps_and_keys(url)
            if not mpd or not keys:
                return False, "Failed to get MPD or keys"
            
            name = f"classplus_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            keys_string = " ".join([f"--key {key}" for key in keys])
            
            result = await helper.decrypt_and_merge_video(
                mpd, keys_string, "downloads", name, quality
            )
            
            if result:
                return True, result
            else:
                return False, "ClassPlus download failed"
                
        except Exception as e:
            return False, str(e)
    
    async def _download_testbook(self, url: str, quality: str) -> tuple[bool, str]:
        """Download TestBook content"""
        # Similar to ClassPlus but with TestBook specific handling
        return await self._download_classplus(url, quality)
    
    async def _download_pdf(self, url: str) -> tuple[bool, str]:
        """Download PDF file"""
        try:
            name = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if "cwmediabkt99" in url:
                # Use cloudscraper for specific domains
                import cloudscraper
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url.replace(" ", "%20"))
                
                if response.status_code == 200:
                    filename = f"{name}.pdf"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    return True, filename
                else:
                    return False, f"HTTP {response.status_code}"
            else:
                # Use yt-dlp for other PDFs
                cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                result = os.system(cmd)
                if result == 0:
                    return True, f"{name}.pdf"
                else:
                    return False, f"Download failed with code {result}"
                    
        except Exception as e:
            return False, str(e)
    
    async def _download_video(self, url: str, quality: str) -> tuple[bool, str]:
        """Download generic video"""
        try:
            name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cmd = f'yt-dlp -f "best[height<={quality}]" -o "{name}.%(ext)s" "{url}"'
            
            result = await helper.download_video(url, cmd, name)
            if result:
                return True, result
            else:
                return False, "Video download failed"
                
        except Exception as e:
            return False, str(e)
    
    async def _download_generic(self, url: str) -> tuple[bool, str]:
        """Download generic file"""
        try:
            name = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cmd = f'yt-dlp -o "{name}.%(ext)s" "{url}"'
            
            result = os.system(cmd)
            if result == 0:
                # Find the downloaded file
                for ext in ['.mp4', '.mkv', '.pdf', '.zip', '.mp3']:
                    if os.path.exists(f"{name}{ext}"):
                        return True, f"{name}{ext}"
                return False, "Downloaded file not found"
            else:
                return False, f"Download failed with code {result}"
                
        except Exception as e:
            return False, str(e)
    
    async def _handle_successful_download(self, message: Message, filename: str,
                                        download_id: int, platform: str, 
                                        file_type: str, status_msg: Message):
        """Handle successful download - upload and log"""
        try:
            # Get file info
            file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            file_size_str = format_file_size(file_size)
            
            # Update status
            await status_msg.edit_text(
                f"📤 **Uploading**\n\n"
                f"**File:** {os.path.basename(filename)}\n"
                f"**Size:** {file_size_str}\n"
                f"**Status:** Uploading to Telegram..."
            )
            
            # Upload to Telegram
            if file_type == "video":
                sent_msg = await helper.send_vid(
                    self.bot, message, f"📹 **{platform}**\n📏 **Size:** {file_size_str}", 
                    filename, "/d", os.path.basename(filename), status_msg
                )
            else:
                sent_msg = await message.reply_document(
                    document=filename,
                    caption=f"📄 **{platform}**\n📏 **Size:** {file_size_str}"
                )
            
            # Log to channels if enabled
            if self.log_service.enabled and sent_msg:
                user_info = {
                    'user_id': message.from_user.id,
                    'username': message.from_user.username,
                    'name': f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
                }
                
                download_info = {
                    'url': self.active_downloads[download_id]['url'],
                    'platform': platform,
                    'file_type': file_type,
                    'file_size': file_size_str
                }
                
                await self.log_service.log_file_upload(
                    sent_msg, user_info, download_info, download_id
                )
            
            # Update database
            await download_manager.update_download_status(
                download_id, DownloadStatus.COMPLETED,
                telegram_file_id=sent_msg.document.file_id if sent_msg.document else None
            )
            
            # Clean up
            if os.path.exists(filename):
                os.remove(filename)
            
            await status_msg.delete()
            
        except Exception as e:
            print(f"Error handling successful download: {e}")
            await download_manager.update_download_status(
                download_id, DownloadStatus.FAILED, str(e)
            )
    
    async def _handle_failed_download(self, message: Message, error: str,
                                    download_id: int, status_msg: Message):
        """Handle failed download"""
        try:
            await status_msg.edit_text(
                f"❌ **Download Failed**\n\n"
                f"**Error:** {error}\n"
                f"**Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # Update database
            await download_manager.update_download_status(
                download_id, DownloadStatus.FAILED, error
            )
            
        except Exception as e:
            print(f"Error handling failed download: {e}")
    
    async def _process_batch_item(self, message: Message, url: str, name: str,
                                index: int, batch_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Process single item in batch download"""
        try:
            platform = extract_platform_from_url(url)
            file_type = detect_file_type(name, url)
            
            # Track in stats
            batch_stats['platforms'][platform] = batch_stats['platforms'].get(platform, 0) + 1
            batch_stats['file_types'][file_type] = batch_stats['file_types'].get(file_type, 0) + 1
            
            # Download file
            success, result = await self._download_file(url, "720", message)
            
            if success:
                batch_stats['successful'] += 1
                file_size = os.path.getsize(result) if os.path.exists(result) else 0
                batch_stats['total_size_bytes'] += file_size
                
                # Upload file (simplified for batch)
                try:
                    if file_type == "video":
                        await message.reply_video(
                            video=result,
                            caption=f"📹 **{name}** ({platform})"
                        )
                    else:
                        await message.reply_document(
                            document=result,
                            caption=f"📄 **{name}** ({platform})"
                        )
                    
                    # Clean up
                    if os.path.exists(result):
                        os.remove(result)
                        
                except Exception as upload_error:
                    print(f"Upload error for {name}: {upload_error}")
                
                return {
                    'index': index,
                    'name': name,
                    'url': url,
                    'platform': platform,
                    'file_type': file_type,
                    'status': 'completed',
                    'file_size_bytes': file_size
                }
            else:
                batch_stats['failed'] += 1
                return {
                    'index': index,
                    'name': name,
                    'url': url,
                    'platform': platform,
                    'file_type': file_type,
                    'status': 'failed',
                    'error': result
                }
                
        except Exception as e:
            batch_stats['failed'] += 1
            return {
                'index': index,
                'name': name,
                'url': url,
                'status': 'failed',
                'error': str(e)
            }
    
    async def _update_batch_progress(self, progress_msg: Message, current: int,
                                   total: int, batch_stats: Dict[str, Any], 
                                   status: str):
        """Update batch progress message"""
        try:
            percentage = round((current / total) * 100, 1)
            progress_bar = "█" * int(percentage // 5) + "░" * (20 - int(percentage // 5))
            
            elapsed_time = datetime.now() - batch_stats['start_time']
            elapsed_str = format_duration(int(elapsed_time.total_seconds()))
            
            text = (
                f"📦 **Batch Download Progress**\n\n"
                f"**Progress:** {current}/{total} ({percentage}%)\n"
                f"{progress_bar}\n\n"
                f"**Successful:** {batch_stats['successful']}\n"
                f"**Failed:** {batch_stats['failed']}\n"
                f"**Elapsed Time:** {elapsed_str}\n"
                f"**Current:** {status}"
            )
            
            await progress_msg.edit_text(text)
            
        except Exception as e:
            print(f"Error updating batch progress: {e}")
    
    async def _send_batch_summary(self, message: Message, batch_stats: Dict[str, Any],
                                progress_msg: Message):
        """Send final batch summary"""
        try:
            total_time = format_duration(int(batch_stats['total_time'].total_seconds()))
            total_size = format_file_size(batch_stats['total_size_bytes'])
            
            # Create file type breakdown
            file_type_text = "\n".join([
                f"  • {ftype.title()}: {count}" 
                for ftype, count in batch_stats['file_types'].items()
            ])
            
            summary_text = (
                f"📊 **Batch Download Complete**\n\n"
                f"**Total Files:** {batch_stats['total_files']}\n"
                f"**Successful:** {batch_stats['successful']} ✅\n"
                f"**Failed:** {batch_stats['failed']} ❌\n"
                f"**Total Size:** {total_size}\n"
                f"**Total Time:** {total_time}\n\n"
                f"**File Types:**\n{file_type_text}\n\n"
                f"**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await progress_msg.edit_text(summary_text)
            
        except Exception as e:
            print(f"Error sending batch summary: {e}")
