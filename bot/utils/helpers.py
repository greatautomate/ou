"""
Helper utilities for the bot
"""
import os
import re
import asyncio
import aiofiles
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse
import mimetypes

def format_user_info(user_id: int, username: str = None, 
                    first_name: str = None, last_name: str = None) -> str:
    """Format user information for display"""
    parts = []
    
    if first_name:
        name_parts = [first_name]
        if last_name:
            name_parts.append(last_name)
        parts.append(f"**Name:** {' '.join(name_parts)}")
    
    if username:
        parts.append(f"**Username:** @{username}")
    
    parts.append(f"**User ID:** `{user_id}`")
    
    return "\n".join(parts)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def format_duration(seconds: int) -> str:
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"

def extract_platform_from_url(url: str) -> str:
    """Extract platform name from URL"""
    domain_patterns = {
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'drive.google.com': 'Google Drive',
        'classplusapp.com': 'ClassPlus',
        'testbook.com': 'TestBook',
        'visionias.in': 'VisionIAS',
        'physicswallah.live': 'Physics Wallah',
        'instagram.com': 'Instagram',
        'facebook.com': 'Facebook',
        'twitter.com': 'Twitter',
        'tiktok.com': 'TikTok'
    }
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        for pattern, platform in domain_patterns.items():
            if pattern in domain:
                return platform
        
        return domain.replace('www.', '').title()
    except:
        return "Unknown"

def detect_file_type(filename: str, url: str = None) -> str:
    """Detect file type from filename or URL"""
    if not filename and url:
        filename = url
    
    if not filename:
        return "unknown"
    
    filename = filename.lower()
    
    # Video formats
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    if any(filename.endswith(ext) for ext in video_extensions):
        return "video"
    
    # Audio formats
    audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']
    if any(filename.endswith(ext) for ext in audio_extensions):
        return "audio"
    
    # Image formats
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    if any(filename.endswith(ext) for ext in image_extensions):
        return "image"
    
    # Document formats
    document_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']
    if any(filename.endswith(ext) for ext in document_extensions):
        return "document"
    
    # Archive formats
    archive_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
    if any(filename.endswith(ext) for ext in archive_extensions):
        return "archive"
    
    return "other"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove multiple spaces and replace with single space
    filename = re.sub(r'\s+', ' ', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    return filename

def extract_video_info(url: str) -> Dict[str, Any]:
    """Extract video information from URL"""
    info = {
        'platform': extract_platform_from_url(url),
        'url': url,
        'is_playlist': False,
        'is_live': False
    }
    
    # YouTube specific checks
    if 'youtube.com' in url or 'youtu.be' in url:
        if 'playlist' in url or 'list=' in url:
            info['is_playlist'] = True
        if 'live' in url:
            info['is_live'] = True
    
    return info

async def safe_file_operation(operation: str, file_path: str, 
                             content: str = None) -> Tuple[bool, str]:
    """Safely perform file operations"""
    try:
        if operation == "read":
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return True, content
        
        elif operation == "write":
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            return True, "File written successfully"
        
        elif operation == "delete":
            if os.path.exists(file_path):
                os.remove(file_path)
            return True, "File deleted successfully"
        
        else:
            return False, "Invalid operation"
    
    except Exception as e:
        return False, str(e)

def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Create a text progress bar"""
    if total == 0:
        return "█" * length
    
    filled_length = int(length * current // total)
    bar = "█" * filled_length + "░" * (length - filled_length)
    percentage = round(100 * current / total, 1)
    
    return f"{bar} {percentage}%"

def parse_quality_from_url(url: str) -> Optional[str]:
    """Parse video quality from URL if available"""
    quality_patterns = [
        r'(\d+)p',  # 720p, 1080p, etc.
        r'(\d+)x(\d+)',  # 1920x1080, etc.
    ]
    
    for pattern in quality_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            if 'x' in match.group():
                # Extract height from resolution
                width, height = match.groups()
                return f"{height}p"
            else:
                return match.group(1) + "p"
    
    return None

def validate_url(url: str) -> Tuple[bool, str]:
    """Validate if URL is properly formatted"""
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return False, "URL must include protocol (http:// or https://)"
        
        if not parsed.netloc:
            return False, "URL must include domain name"
        
        if parsed.scheme not in ['http', 'https']:
            return False, "Only HTTP and HTTPS URLs are supported"
        
        return True, "Valid URL"
    
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"

def create_download_stats(downloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create statistics from download list"""
    if not downloads:
        return {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'total_size': '0 B',
            'file_types': {},
            'platforms': {}
        }
    
    successful = len([d for d in downloads if d.get('status') == 'completed'])
    failed = len([d for d in downloads if d.get('status') == 'failed'])
    
    # Calculate total size
    total_size_bytes = sum(d.get('file_size_bytes', 0) for d in downloads)
    
    # Count file types
    file_types = {}
    for download in downloads:
        file_type = download.get('file_type', 'unknown')
        file_types[file_type] = file_types.get(file_type, 0) + 1
    
    # Count platforms
    platforms = {}
    for download in downloads:
        platform = download.get('platform', 'unknown')
        platforms[platform] = platforms.get(platform, 0) + 1
    
    return {
        'total_files': len(downloads),
        'successful': successful,
        'failed': failed,
        'total_size': format_file_size(total_size_bytes),
        'total_size_bytes': total_size_bytes,
        'file_types': file_types,
        'platforms': platforms
    }

def generate_unique_filename(base_name: str, extension: str, 
                           existing_files: List[str]) -> str:
    """Generate unique filename to avoid conflicts"""
    counter = 1
    filename = f"{base_name}.{extension}"
    
    while filename in existing_files:
        filename = f"{base_name}_{counter}.{extension}"
        counter += 1
    
    return filename

async def cleanup_old_files(directory: str, max_age_hours: int = 24):
    """Clean up old files from directory"""
    if not os.path.exists(directory):
        return
    
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    cleaned_count = 0
    
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_time < cutoff_time:
                    os.remove(file_path)
                    cleaned_count += 1
        
        print(f"🧹 Cleaned up {cleaned_count} old files from {directory}")
    
    except Exception as e:
        print(f"❌ Error cleaning up files: {e}")

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def truncate_text(text: str, max_length: int = 4000) -> str:
    """Truncate text to fit Telegram message limits"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."
