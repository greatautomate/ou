"""
Configuration management for Medusa Bot
"""
import os
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class BotConfig:
    """Bot configuration settings"""
    # Telegram Bot Settings
    api_id: int
    api_hash: str
    bot_token: str
    owner: int
    owner_username: str
    credit: str
    
    # Database Settings
    database_url: str
    
    # File Settings
    cookies_file_path: str
    max_file_size_mb: int
    download_timeout: int
    max_concurrent_downloads: int
    
    # Log Channel Settings
    log_channels: List[int]
    backup_log_channels: List[int]
    
    # Performance Settings
    chunk_size: int
    retry_attempts: int
    retry_delay: int
    
    # Feature Flags
    enable_analytics: bool
    enable_download_history: bool
    enable_progress_tracking: bool
    enable_auto_cleanup: bool
    
    # Rate Limiting
    max_downloads_per_user_per_hour: int
    max_downloads_per_user_per_day: int
    
    # Quality Settings
    default_video_quality: str
    available_qualities: List[str]

class ConfigManager:
    """Manages bot configuration"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> BotConfig:
        """Load configuration from environment variables"""
        return BotConfig(
            # Telegram Bot Settings - Environment variables required
            api_id=int(os.getenv("API_ID")),
            api_hash=os.getenv("API_HASH"),
            bot_token=os.getenv("BOT_TOKEN"),
            owner=int(os.getenv("OWNER")),
            owner_username=os.getenv("OWNER_USERNAME", "@medusaXD"),
            credit="★彡[ᴍᴇᴅᴜꜱᴀxᴅ]彡★",
            
            # Database Settings
            database_url=os.getenv("DATABASE_URL", "postgresql://user:password@localhost/medusa_bot"),
            
            # File Settings
            cookies_file_path=os.getenv("COOKIES_FILE_PATH", "youtube_cookies.txt"),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "2000")),  # 2GB Telegram limit
            download_timeout=int(os.getenv("DOWNLOAD_TIMEOUT", "3600")),  # 1 hour
            max_concurrent_downloads=int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5")),
            
            # Log Channel Settings
            log_channels=self._parse_int_list(os.getenv("LOG_CHANNELS", "")),
            backup_log_channels=self._parse_int_list(os.getenv("BACKUP_LOG_CHANNELS", "")),
            
            # Performance Settings
            chunk_size=int(os.getenv("CHUNK_SIZE", "1048576")),  # 1MB chunks
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "2")),  # seconds
            
            # Feature Flags
            enable_analytics=os.getenv("ENABLE_ANALYTICS", "true").lower() == "true",
            enable_download_history=os.getenv("ENABLE_DOWNLOAD_HISTORY", "true").lower() == "true",
            enable_progress_tracking=os.getenv("ENABLE_PROGRESS_TRACKING", "true").lower() == "true",
            enable_auto_cleanup=os.getenv("ENABLE_AUTO_CLEANUP", "true").lower() == "true",
            
            # Rate Limiting
            max_downloads_per_user_per_hour=int(os.getenv("MAX_DOWNLOADS_PER_USER_PER_HOUR", "50")),
            max_downloads_per_user_per_day=int(os.getenv("MAX_DOWNLOADS_PER_USER_PER_DAY", "200")),
            
            # Quality Settings
            default_video_quality=os.getenv("DEFAULT_VIDEO_QUALITY", "720"),
            available_qualities=self._parse_string_list(os.getenv("AVAILABLE_QUALITIES", "144,240,360,480,720,1080"))
        )
    
    def _parse_int_list(self, value: str) -> List[int]:
        """Parse comma-separated string to list of integers"""
        if not value:
            return []
        try:
            return [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
        except:
            return []
    
    def _parse_string_list(self, value: str) -> List[str]:
        """Parse comma-separated string to list of strings"""
        if not value:
            return []
        return [x.strip() for x in value.split(',') if x.strip()]
    
    def get_log_channels(self) -> List[int]:
        """Get all log channels (primary + backup)"""
        return self.config.log_channels + self.config.backup_log_channels
    
    def is_log_channel_enabled(self) -> bool:
        """Check if log channel feature is enabled"""
        return len(self.config.log_channels) > 0
    
    def get_download_limits(self, user_id: int) -> dict:
        """Get download limits for a user"""
        # Could be extended to have different limits for different users
        return {
            "hourly": self.config.max_downloads_per_user_per_hour,
            "daily": self.config.max_downloads_per_user_per_day
        }
    
    def get_quality_options(self) -> List[str]:
        """Get available video quality options"""
        return self.config.available_qualities
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if not self.config.bot_token:
            issues.append("BOT_TOKEN is required")
        
        if not self.config.api_id or not self.config.api_hash:
            issues.append("API_ID and API_HASH are required")
        
        if self.config.max_file_size_mb > 2000:
            issues.append("MAX_FILE_SIZE_MB cannot exceed 2000 (Telegram limit)")
        
        if self.config.max_concurrent_downloads > 10:
            issues.append("MAX_CONCURRENT_DOWNLOADS should not exceed 10 for stability")
        
        if self.config.retry_attempts > 5:
            issues.append("RETRY_ATTEMPTS should not exceed 5")
        
        return issues

# Global configuration instance
config = ConfigManager()

# Validate configuration on import
config_issues = config.validate_config()
if config_issues:
    print("⚠️ Configuration issues found:")
    for issue in config_issues:
        print(f"  - {issue}")
else:
    print("✅ Configuration loaded successfully")

# Export commonly used values
API_ID = config.config.api_id
API_HASH = config.config.api_hash
BOT_TOKEN = config.config.bot_token
OWNER = config.config.owner
OWNER_USERNAME = config.config.owner_username
CREDIT = config.config.credit
DATABASE_URL = config.config.database_url
LOG_CHANNELS = config.config.log_channels
MAX_FILE_SIZE_MB = config.config.max_file_size_mb
RETRY_ATTEMPTS = config.config.retry_attempts
ENABLE_ANALYTICS = config.config.enable_analytics
