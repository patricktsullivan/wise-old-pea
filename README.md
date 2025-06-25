# 🎮 Wise Old Pea Bot

A comprehensive Discord bot for running Old School RuneScape events with automated challenge releases, timing systems, and interactive gameplay. Perfect for clans, communities, and gaming groups who want to organize engaging OSRS competitions.

## ✨ Features

### 🎯 **Event Management**
- **Automated Challenge Releases**: Set up events that release challenges on a schedule (hourly, daily, etc.)
- **Multiple Challenge Types**: Trivia, speed runs, races, location finding, and more
- **Event Lifecycle**: Complete event creation, management, and conclusion workflows
- **Admin Controls**: Force releases, reset progress, view detailed statistics

### 🏆 **Challenge Types**
- **📍 Pea's Place**: Progressive location-finding with timed hint releases
- **🧠 Scape Smarts**: OSRS trivia with multiple question formats
- **⚡ Speed Runs**: Timer-based challenges (Fight Caves, spell book swapping)
- **🏃 Race Challenges**: Timed competitions with inventory matching
- **🎮 Interactive Minigames**: Snake game, prop hunt, and survival challenges

### 💬 **Smart DM System**
- **Challenge-Specific Handlers**: Each challenge type has custom DM interactions
- **Progressive Hints**: Automatic hint releases for stuck players
- **Evidence Collection**: Smart screenshot and URL detection
- **Skip System**: Allow players to skip difficult stages with time penalties

### 📊 **Scoring & Progress**
- **Real-Time Tracking**: Live progress monitoring for all participants
- **Multiple Metrics**: Time-based scoring, trivia accuracy, evidence quality
- **Admin Dashboard**: Comprehensive participant overview and individual analysis
- **Historical Data**: Complete event archives and player statistics

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Server with "Manage Guild" permissions for admins

### Option 1: Standard Installation

#### 1. Installation

```bash
# Clone or download the bot files
git clone [your-repo-url]
cd wise-old-pea-bot

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configuration

1. **Create your bot token file:**
   ```bash
   # Create .env file
   echo "DISCORD_BOT_TOKEN=your_bot_token_here" > .env
   ```

2. **Verify challenge_rules.json exists** (included in repository)

3. **Set up bot permissions in Discord:**
   - Send Messages
   - Send Messages in Threads  
   - Read Message History
   - Add Reactions
   - Use Slash Commands
   - Send DMs to users

#### 3. Launch

```bash
# Windows
./start_bot.bat

# Linux/Mac  
./start_bot.sh

# Or directly with Python
python wise_old_pea.py
```

### Option 2: Docker Deployment

#### 1. Quick Setup
```bash
# Clone the repository
git clone [your-repo-url]
cd wise-old-pea-bot

# Create environment file
cp .env.template .env
# Edit .env with your bot token

# Start with Docker Compose
docker-compose up -d
```

#### 2. Docker Commands
```bash
# View logs
docker-compose logs -f

# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart

# Update and rebuild
git pull
docker-compose up -d --build
```

#### 3. Docker Benefits
- ✅ **Isolated Environment**: No conflicts with system Python
- ✅ **Easy Updates**: Simple rebuild and restart process
- ✅ **Resource Management**: Built-in memory and CPU limits
- ✅ **Auto-Restart**: Automatically restarts if bot crashes
- ✅ **Consistent Deployment**: Same environment across servers

## 📖 User Guide

### 🔗 **Getting Started**
```
!link_account <your_osrs_username>   # Link your OSRS account
!join <event_name>                   # Join an active event
!my_scores                           # View your progress
```

### 🎯 **Challenge Commands**
```
!join <challenge_name>               # Join a specific challenge
!start <challenge_name>              # Begin your attempt (starts timer)
!finish <challenge_name>             # Complete the challenge
!evidence [challenge_name]           # Submit screenshots/proof
!skip                                # Skip to next stage (DM challenges only)
```

### 📊 **Information Commands**
```
!help                                # Show all available commands
!help <command_name>                 # Get detailed help for a command
!my_scores                           # View your personal progress
```

## 🛡️ Admin Guide

### 📅 **Event Management**
```
!create_event                        # Interactive event creation (via DM)
!event_status                        # Check current event progress
!force_release                       # Manually release next challenge
```

### 👥 **User Management**
```
!admin_scores [username]             # View all or specific user scores
!set_stage <username> <stage>        # Manually set user's challenge stage
!reset <username> <challenge>        # Reset user's challenge progress
```

### 🔧 **Debug Commands**
```
!peas_place_debug <username>         # Debug Pea's Place state
!test_peas_advance <username>        # Test Pea's Place advancement
!debug_media <location> <stage>      # Test media URL lookup
!list_media                          # List all available media keys
```

## 🎮 Challenge Types Explained

### 📍 **Pea's Place**
Progressive location-finding challenge:
- Start with a zoomed-in screenshot
- Every 2-5 minutes, receive a more zoomed-out view  
- Submit screenshot evidence when you find the location
- Advance through 10 locations with 5 progressive hints each

### 🧠 **Scape Smarts** 
OSRS trivia with various question formats:
- Multiple choice questions
- Exact match answers
- List-based questions (name X items)
- Ordered rankings
- Gear setup questions

### ⚡ **Speed Run Challenges**
Timer-based individual competitions:
- TzTik-TzTok (Fight Caves speedrun)
- EXP Share the Love (gain XP in every skill)
- Spellbook Swap (cast spells from all 4 spellbooks)

### 🏃 **Race Challenges**
Timed group competitions:
- Alchemy, Old School Magic (create high alch value)
- Spawn Camping (solve anagrams, find item spawns)
- Shopping List (match inventory to given image)
- Alphabet Soup (kill NPCs A-Z)

## ⚙️ Configuration

### 🔧 **Timing Settings**
Edit these in the respective files:

**Pea's Place Hint Timing** (`wise_old_pea.py`):
```python
TIME_DELAY_MINUTES = 5  # Minutes between progressive hints
```

**Challenge Release Interval** (set during event creation):
- Configurable per event
- Can be hours, days, or weeks
- Supports manual override with `!force_release`

### 📁 **File Structure**
```
wise-old-pea-bot/
├── wise_old_pea.py           # Main bot entry point
├── database.py               # Data persistence layer
├── event_manager.py          # Event lifecycle management
├── challenge_handlers.py     # Challenge-specific logic
├── admin_commands.py         # Admin command implementations
├── user_commands.py          # User command implementations  
├── utils.py                  # Utility functions
├── challenge_rules.json      # Challenge definitions and media
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
├── .env.template            # Environment template
├── start_bot.bat            # Windows launcher
├── start_bot.sh             # Linux/Mac launcher
├── setup.sh                 # Automated setup script
├── Dockerfile               # Docker container definition
├── docker-compose.yml       # Docker deployment config
├── .dockerignore           # Docker build exclusions
├── README.md               # Full documentation
├── INSTALL.md              # Quick installation guide
├── data/                   # Database files (auto-created)
└── logs/                   # Log files (auto-created)
```

### 🗄️ **Database**
- **Type**: JSON file-based (no external database required)
- **Location**: `data/wise_old_pea_data.json` (auto-created)
- **Backup**: Automatically saved after each operation
- **Structure**: Accounts and events with full challenge progress

## 🔍 Troubleshooting

### ❌ **Common Issues**

**"No active event found"**
- Ensure an admin has created an event with `!create_event`
- Check event status with `!event_status`

**"Cannot send DM to user"**  
- User needs to allow DMs from server members
- Check Discord privacy settings

**"Challenge not found"**
- Use exact challenge names from announcements
- Challenge names use underscores: `peas_place`, `scape_smarts`

**Pea's Place images not advancing**
- Check user has `intents.members = True` in bot setup
- Use `!peas_place_debug <username>` to check state
- Use `!test_peas_advance <username>` to manually advance

### 📋 **Debug Commands**
```bash
# Check bot logs
tail -f logs/wise_old_pea_YYYYMMDD.log

# Check error logs only  
tail -f logs/errors_YYYYMMDD.log

# Test specific challenge media
!debug_media 1 2

# Test user advancement
!test_peas_advance username
```

### 🆘 **Getting Help**

1. **Check the logs** in the `logs/` directory
2. **Use admin debug commands** to diagnose issues
3. **Verify bot permissions** in Discord server settings
4. **Check user DM settings** for challenge delivery issues

## 🏗️ Architecture

### 📋 **Core Components**

**Event Manager**: Handles event creation, challenge releases, and timing
**Challenge Handlers**: Type-specific logic for trivia, races, speed runs, etc.  
**Database Layer**: JSON-based persistence with automatic backups
**Command System**: Organized user and admin command interfaces
**Background Tasks**: Automatic challenge releases and timeout handling

### 🔄 **Event Flow**
1. **Admin creates event** → Sets duration, release schedule, challenges
2. **Bot releases challenges** → Automatic timing or manual override  
3. **Users join and participate** → DM interactions, evidence submission
4. **Progress tracking** → Real-time scoring and advancement
5. **Event conclusion** → Final scoring and historical archival

### 🎯 **Challenge Lifecycle**
```
Not Started → Active → Finished
     ↑           ↓        ↓
   join      start    finish/timeout
              ↓
         DM interactions, evidence, progression
```

## 📄 License

This project is provided as-is for community use. Please respect Discord's Terms of Service and API guidelines when running the bot.

---

*Built for the Old School RuneScape community with ❤️*