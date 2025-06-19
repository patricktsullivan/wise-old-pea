# config.py - Enhanced Configuration
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
COMMAND_PREFIX = '!'

# API Configuration
WISEOLDMAN_API_URL = 'https://api.wiseoldman.net/v2'
WISEOLDMAN_RATE_LIMIT = 1.0  # seconds between requests

# Event Configuration
MAX_EVENT_DURATION = 168  # 7 days in hours
MIN_CHALLENGE_INTERVAL = 1  # Minimum 1 hour between challenges
MAX_TRIVIA_QUESTIONS = 50
MAX_BINGO_TASKS = 25
MAX_CHALLENGES_PER_EVENT = 20

# Database Configuration
DATA_DIRECTORY = 'data'
EVENTS_FILE = 'events.json'
ACCOUNTS_FILE = 'osrs_accounts.json'
BACKUP_DIRECTORY = 'backups'

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FILE = 'bot.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Event Type Configurations
EVENT_TYPES = {
    'MULTIPLE_CHALLENGES': {
        'min_interval': 1,  # hours
        'max_challenges': 20,
        'default_challenge_duration': 24  # hours
    },
    'EXPERIENCE_GAINED': {
        'tracking_period': '1d',  # WiseOldMan period
        'leaderboard_refresh': 24  # hours
    },
    'BOSSES_KILLED': {
        'tracking_period': '1d',
        'leaderboard_refresh': 24
    },
    'TRIVIA': {
        'max_questions': 50,
        'question_timeout': 300  # seconds
    },
    'BINGO': {
        'max_tasks': 25,
        'reminder_intervals': [0.75, 0.95]  # fraction of event duration
    }
}

# Discord Configuration
EMBED_COLORS = {
    'success': 0x00ff00,    # Green
    'error': 0xff0000,      # Red
    'info': 0x0099ff,       # Blue
    'warning': 0xffff00,    # Yellow
    'event': 0x9932cc,      # Purple
    'leaderboard': 0xffd700  # Gold
}

# Task Intervals (in minutes)
EVENT_SCHEDULER_INTERVAL = 10
LEADERBOARD_TASK_INTERVAL = 1440  # 24 hours
BACKUP_TASK_INTERVAL = 360  # 6 hours

# Permissions
ADMIN_COMMANDS = [
    'create_event',
    'start_event',
    'pause_event',
    'resume_event',
    'end_event',
    'delete_event'
]

# .env template for reference
ENV_TEMPLATE = """
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_bot_token_here

# Optional: Database Configuration (for future SQLite/PostgreSQL support)
# DATABASE_URL=sqlite:///events.db

# Optional: Webhook URLs for notifications
# DISCORD_WEBHOOK_URL=your_webhook_url_here

# Optional: Additional API Keys
# CUSTOM_API_KEY=your_api_key_here
"""

def validate_config():
    """Validate configuration settings"""
    errors = []
    
    if not BOT_TOKEN or BOT_TOKEN == 'your_bot_token_here':
        errors.append("DISCORD_BOT_TOKEN not set in .env file")
    
    if not os.path.exists(DATA_DIRECTORY):
        try:
            os.makedirs(DATA_DIRECTORY)
        except Exception as e:
            errors.append(f"Cannot create data directory: {e}")
    
    return errors

def get_event_config(event_type):
    """Get configuration for specific event type"""
    return EVENT_TYPES.get(event_type.upper(), {})

def get_embed_color(color_type):
    """Get embed color for specific type"""
    return EMBED_COLORS.get(color_type, EMBED_COLORS['info'])