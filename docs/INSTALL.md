# 🚀 Quick Installation Guide

## Prerequisites
- **Python 3.8+** ([Download here](https://python.org))
- **Discord Bot Token** ([Get one here](https://discord.com/developers/applications))

## 📦 Installation

### Option 1: Automatic Setup (Linux/Mac)
```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create environment file:**
   ```bash
   cp .env.template .env
   # Edit .env and add your bot token
   ```

3. **Make scripts executable (Linux/Mac):**
   ```bash
   chmod +x start_bot.sh
   ```

## 🎯 Get Your Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → Give it a name
3. Go to "Bot" section → Click "Add Bot"
4. Under "Token" section → Click "Copy"
5. Paste the token in your `.env` file

## 🔧 Bot Permissions

When inviting your bot to a server, ensure it has:
- ✅ Send Messages
- ✅ Send Messages in Threads
- ✅ Read Message History
- ✅ Add Reactions
- ✅ Use External Emojis
- ✅ Send DMs to Users

**Quick Invite Link Template:**
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=274877991936&scope=bot
```
*(Replace YOUR_BOT_ID with your actual bot's client ID)*

## 🚀 Launch

### Windows:
```cmd
start_bot.bat
```

### Linux/Mac:
```bash
./start_bot.sh
```

### Direct Python:
```bash
python wise_old_pea.py
```

## ✅ Verify Installation

1. **Bot comes online** in your Discord server
2. **Run test command:** `!help`
3. **Link your account:** `!link_account your_osrs_name`
4. **Admin test:** `!create_event` (if you have Manage Guild permissions)

## 🆘 Troubleshooting

### "ModuleNotFoundError: No module named 'discord'"
```bash
pip install discord.py
```

### "discord.errors.LoginFailure: Improper token"
- Check your `.env` file has the correct bot token
- Make sure there are no extra spaces or quotes

### Bot doesn't respond to commands
- Check bot has required permissions in your server
- Verify bot is online (green status)
- Try `!help` command

### "Cannot send DM to user"
- User needs to allow DMs from server members
- Check Discord privacy settings

## 📁 File Structure After Setup
```
wise-old-pea-bot/
├── wise_old_pea.py
├── challenge_rules.json
├── .env                    ← Your bot token
├── requirements.txt
├── start_bot.sh           ← Executable
├── start_bot.bat
├── data/                  ← Auto-created
└── logs/                  ← Auto-created
```

## 🎮 First Event

1. **Create event:** `!create_event` (admin only)
2. **Users join:** `!join event_name`
3. **Start challenges:** `!start challenge_name`
4. **Submit evidence:** `!evidence`
5. **View progress:** `!my_scores`

---
🎉 **You're ready to run OSRS events!** Check the full README.md for detailed usage instructions.