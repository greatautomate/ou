#🇳‌🇮‌🇰‌🇭‌🇮‌🇱‌
# Add your details here and then deploy by clicking on HEROKU Deploy button
from os import environ

# Environment variables - must be set in deployment platform
def get_env_var(var_name, var_type=str):
    """Get environment variable with proper error handling"""
    value = environ.get(var_name)
    if value is None:
        raise ValueError(f"❌ Environment variable '{var_name}' is not set! Please configure it in your deployment platform.")

    try:
        if var_type == int:
            return int(value)
        return value
    except ValueError:
        raise ValueError(f"❌ Environment variable '{var_name}' has invalid value '{value}'. Expected {var_type.__name__}.")

# Required environment variables
API_ID = get_env_var("API_ID", int)
API_HASH = get_env_var("API_HASH")
BOT_TOKEN = get_env_var("BOT_TOKEN")
OWNER = get_env_var("OWNER", int)
OWNER_USERNAME = environ.get("OWNER_USERNAME", "@medusaXD")
# Clickable credit link - when clicked, redirects to owner's Telegram profile
CREDIT = "[★彡[ᴍᴇᴅᴜꜱᴀxᴅ]彡★](https://t.me/medusaXD)"
# Credits: ★彡[ᴍᴇᴅᴜꜱᴀxᴅ]彡★ = https://t.me/medusaXD

# Log Channel Configuration
def parse_channel_list(env_var_name):
    """Parse comma-separated channel IDs from environment variable"""
    channels_env = environ.get(env_var_name, '')
    if not channels_env:
        return []
    try:
        return [int(channel_id.strip()) for channel_id in channels_env.split(',') if channel_id.strip().isdigit()]
    except ValueError:
        print(f"⚠️ Warning: Invalid channel IDs in {env_var_name}")
        return []

# Log Channels - Primary log channels for file logging
LOG_CHANNELS_ENV = parse_channel_list("LOG_CHANNELS")
# Hardcoded log channels as requested
HARDCODED_LOG_CHANNELS = [-1002602431995]

# Combine environment and hardcoded channels
LOG_CHANNELS = LOG_CHANNELS_ENV + HARDCODED_LOG_CHANNELS

# Backup Log Channels - Fallback channels if primary channels fail
BACKUP_LOG_CHANNELS_ENV = parse_channel_list("BACKUP_LOG_CHANNELS")
# Hardcoded backup log channels as requested
HARDCODED_BACKUP_LOG_CHANNELS = [-1002602431995]

# Combine environment and hardcoded backup channels
BACKUP_LOG_CHANNELS = BACKUP_LOG_CHANNELS_ENV + HARDCODED_BACKUP_LOG_CHANNELS

# Combined log channels list (remove duplicates)
ALL_LOG_CHANNELS = list(set(LOG_CHANNELS + BACKUP_LOG_CHANNELS))
#WEBHOOK = True  # Don't change this
#PORT = int(os.environ.get("PORT", 8080))  # Default to 8000 if not set
