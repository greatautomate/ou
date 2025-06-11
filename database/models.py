"""
Database models for Medusa Bot
"""
import asyncio
from datetime import datetime
from typing import Optional, List
import asyncpg
import os
from enum import Enum

class DownloadStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FileType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    IMAGE = "image"
    ARCHIVE = "archive"
    OTHER = "other"

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/medusa_bot")
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            await self.create_tables()
            print("✅ Database initialized successfully")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            # Fallback to in-memory storage
            self.pool = None
    
    async def create_tables(self):
        """Create database tables if they don't exist"""
        if not self.pool:
            return
            
        async with self.pool.acquire() as conn:
            # Users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_authorized BOOLEAN DEFAULT FALSE,
                    added_by BIGINT,
                    total_downloads INTEGER DEFAULT 0,
                    total_size_mb FLOAT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    last_activity TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Channels table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id SERIAL PRIMARY KEY,
                    channel_id BIGINT UNIQUE NOT NULL,
                    channel_name VARCHAR(255),
                    owner_id BIGINT NOT NULL,
                    is_log_channel BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Downloads table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    url TEXT NOT NULL,
                    original_filename VARCHAR(500),
                    saved_filename VARCHAR(500),
                    file_type VARCHAR(50),
                    file_size_mb FLOAT,
                    quality VARCHAR(50),
                    platform VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending',
                    error_message TEXT,
                    download_time_seconds INTEGER,
                    telegram_file_id VARCHAR(500),
                    log_channel_message_id INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    INDEX(user_id),
                    INDEX(status),
                    INDEX(created_at)
                )
            ''')
            
            # Analytics table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS analytics (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    total_downloads INTEGER DEFAULT 0,
                    total_users INTEGER DEFAULT 0,
                    total_size_mb FLOAT DEFAULT 0,
                    popular_platform VARCHAR(100),
                    popular_file_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(date)
                )
            ''')
            
            # Bot settings table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            print("✅ Database tables created successfully")

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()

# User management functions
class UserManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def add_user(self, telegram_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None, 
                      added_by: int = None) -> bool:
        """Add a new user to the database"""
        if not self.db.pool:
            return False
            
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO users (telegram_id, username, first_name, last_name, is_authorized, added_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (telegram_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        updated_at = NOW()
                ''', telegram_id, username, first_name, last_name, True, added_by)
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    async def remove_user(self, telegram_id: int) -> bool:
        """Remove user authorization"""
        if not self.db.pool:
            return False
            
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute('''
                    UPDATE users SET is_authorized = FALSE, updated_at = NOW()
                    WHERE telegram_id = $1
                ''', telegram_id)
            return True
        except Exception as e:
            print(f"Error removing user: {e}")
            return False
    
    async def is_authorized(self, telegram_id: int) -> bool:
        """Check if user is authorized"""
        if not self.db.pool:
            return False
            
        try:
            async with self.db.pool.acquire() as conn:
                result = await conn.fetchval('''
                    SELECT is_authorized FROM users WHERE telegram_id = $1
                ''', telegram_id)
            return result or False
        except Exception as e:
            print(f"Error checking authorization: {e}")
            return False
    
    async def get_authorized_users(self) -> List[int]:
        """Get list of all authorized users"""
        if not self.db.pool:
            return []
            
        try:
            async with self.db.pool.acquire() as conn:
                results = await conn.fetch('''
                    SELECT telegram_id FROM users WHERE is_authorized = TRUE
                ''')
            return [row['telegram_id'] for row in results]
        except Exception as e:
            print(f"Error getting authorized users: {e}")
            return []
    
    async def update_activity(self, telegram_id: int):
        """Update user's last activity"""
        if not self.db.pool:
            return
            
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute('''
                    UPDATE users SET last_activity = NOW() WHERE telegram_id = $1
                ''', telegram_id)
        except Exception as e:
            print(f"Error updating activity: {e}")

# Channel management functions
class ChannelManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def add_channel(self, channel_id: int, owner_id: int, 
                         channel_name: str = None, is_log_channel: bool = False) -> bool:
        """Add a new channel"""
        if not self.db.pool:
            return False
            
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO channels (channel_id, channel_name, owner_id, is_log_channel)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (channel_id) DO UPDATE SET
                        channel_name = EXCLUDED.channel_name,
                        owner_id = EXCLUDED.owner_id,
                        is_log_channel = EXCLUDED.is_log_channel
                ''', channel_id, channel_name, owner_id, is_log_channel)
            return True
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False
    
    async def remove_channel(self, channel_id: int) -> bool:
        """Remove a channel"""
        if not self.db.pool:
            return False
            
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute('''
                    DELETE FROM channels WHERE channel_id = $1
                ''', channel_id)
            return True
        except Exception as e:
            print(f"Error removing channel: {e}")
            return False
    
    async def get_authorized_channels(self) -> List[int]:
        """Get list of all authorized channels"""
        if not self.db.pool:
            return []
            
        try:
            async with self.db.pool.acquire() as conn:
                results = await conn.fetch('''
                    SELECT channel_id FROM channels WHERE is_log_channel = FALSE
                ''')
            return [row['channel_id'] for row in results]
        except Exception as e:
            print(f"Error getting authorized channels: {e}")
            return []
    
    async def get_log_channels(self) -> List[int]:
        """Get list of log channels"""
        if not self.db.pool:
            return []
            
        try:
            async with self.db.pool.acquire() as conn:
                results = await conn.fetch('''
                    SELECT channel_id FROM channels WHERE is_log_channel = TRUE
                ''')
            return [row['channel_id'] for row in results]
        except Exception as e:
            print(f"Error getting log channels: {e}")
            return []

# Download tracking functions
class DownloadManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def log_download(self, user_id: int, url: str, filename: str, 
                          file_type: str, file_size_mb: float = 0, 
                          platform: str = None, quality: str = None) -> int:
        """Log a new download"""
        if not self.db.pool:
            return 0
            
        try:
            async with self.db.pool.acquire() as conn:
                download_id = await conn.fetchval('''
                    INSERT INTO downloads (user_id, url, original_filename, file_type, 
                                         file_size_mb, platform, quality, status)
                    VALUES ((SELECT id FROM users WHERE telegram_id = $1), $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                ''', user_id, url, filename, file_type, file_size_mb, platform, quality, DownloadStatus.PENDING.value)
            return download_id
        except Exception as e:
            print(f"Error logging download: {e}")
            return 0
    
    async def update_download_status(self, download_id: int, status: DownloadStatus, 
                                   error_message: str = None, telegram_file_id: str = None,
                                   log_channel_message_id: int = None):
        """Update download status"""
        if not self.db.pool:
            return
            
        try:
            async with self.db.pool.acquire() as conn:
                if status == DownloadStatus.COMPLETED:
                    await conn.execute('''
                        UPDATE downloads SET status = $1, completed_at = NOW(), 
                               telegram_file_id = $2, log_channel_message_id = $3
                        WHERE id = $4
                    ''', status.value, telegram_file_id, log_channel_message_id, download_id)
                else:
                    await conn.execute('''
                        UPDATE downloads SET status = $1, error_message = $2
                        WHERE id = $3
                    ''', status.value, error_message, download_id)
        except Exception as e:
            print(f"Error updating download status: {e}")

# Initialize global database manager
db_manager = DatabaseManager()
user_manager = UserManager(db_manager)
channel_manager = ChannelManager(db_manager)
download_manager = DownloadManager(db_manager)
