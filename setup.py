#!/usr/bin/env python3
"""
Setup script for the Discord Events Bot

Run this script to set up the bot environment:
python setup.py
"""

import os
import sys

def create_env_file():
    """Create .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write('DISCORD_BOT_TOKEN=your_bot_token_here\n')
        print("✅ Created .env file. Please add your Discord bot token.")
    else:
        print("📁 .env file already exists.")

def create_directories():
    """Create necessary directories"""
    dirs = ['logs', 'data', 'backups']
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"📁 Created {dir_name} directory.")

def create_readme():
    """Create README.md with instructions"""
    readme_content = """# Discord Events Bot

A comprehensive Discord bot for running various types of gaming events with WiseOldMan integration.

## Features

- **Multiple Challenge Events**: Staggered challenges released over time
- **Experience Tracking**: Monitor OSRS XP gains via WiseOldMan API
- **Boss Kill Tracking**: Track boss kills during events
- **Trivia Events**: Interactive question and answer sessions
- **Bingo Events**: Complete various tasks for points
- **Leaderboards**: Daily and final rankings
- **Admin Controls**: Event creation and management

## Setup

1. Clone this repository
2. Run setup: `python setup.py`
3. Install dependencies: `pip install -r requirements.txt`
4. Add your Discord bot token to the `.env` file
5. Run the bot: `python enhanced_bot.py`

## Commands

### Admin Commands (Requires Administrator Permission)
- `!create_event` - Start the event creation process
- `!start_event <event_id>` - Start an event
- `!list_events` - List all events

### User Commands
- `!join_event <event_id>` - Join an active event
- `!event_info <event_id>` - Get event details
- `!link_osrs <username>` - Link your OSRS account
- `!leaderboard <event_id>` - View current leaderboard
- `!start_<challenge_name>` - Start a specific challenge
- `!end_<challenge_name>` - End a specific challenge
- `!complete_bingo <task_number>` - Mark bingo task as complete

## Event Types

### Multiple Challenges
- Series of timed challenges released at intervals
- Each challenge has its own tracking and completion
- Supports various challenge types (XP, boss kills, trivia)

### Experience Gained
- Tracks OSRS experience gains via WiseOldMan
- Requires linked OSRS account
- Daily leaderboards and final rankings

### Bosses Killed
- Tracks boss kill counts during event period
- Uses WiseOldMan API for accurate tracking
- Supports all OSRS bosses

### Trivia
- Interactive question and answer sessions
- Supports multiple choice and open-ended questions
- Private message delivery for fairness

### Bingo
- Complete various tasks for points
- Tasks announced at event start
- Progress tracking and reminders

## Requirements

- Python 3.8+
- Discord.py 2.3.0+
- Valid Discord bot token
- Internet connection for WiseOldMan API

## File Structure

```
discord-events-bot/
├── enhanced_bot.py          # Main bot file
├── config.py               # Configuration settings
├── database.py             # Data storage utilities
├── utils.py                # API utilities
├── requirements.txt        # Python dependencies
├── setup.py               # Setup script
├── .env                   # Environment variables (create this)
├── data/                  # Bot data storage
│   ├── events.json        # Event data
│   └── osrs_accounts.json # Linked accounts
├── logs/                  # Log files
└── backups/              # Data backups
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Feel free to use and modify as needed.
"""
    
    if not os.path.exists('README.md'):
        with open('README.md', 'w') as f:
            f.write(readme_content)
        print("📝 Created README.md")

def main():
    print("🚀 Setting up Discord Events Bot...")
    print("=" * 40)
    
    create_env_file()
    create_directories()
    create_readme()
    
    print("\n✅ Setup complete!")
    print("\n📋 Next steps:")
    print("1. Add your Discord bot token to the .env file")
    print("2. Install requirements: pip install -r requirements.txt")
    print("3. Run the bot: python enhanced_bot.py")
    print("\n🔗 Useful links:")
    print("- Discord Developer Portal: https://discord.com/developers/applications")
    print("- WiseOldMan API: https://docs.wiseoldman.net/")
    print("- Discord.py Documentation: https://discordpy.readthedocs.io/")

if __name__ == "__main__":
    main()