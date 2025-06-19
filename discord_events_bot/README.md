Wise Old Pea Discord Bot

Event Types Supported:
Multiple Challenges - Staggered challenges released at set intervals
Experience Gained - Tracks OSRS XP via WiseOldMan API
Bosses Killed - Tracks boss kills via WiseOldMan API
Trivia - Interactive Q&A with multiple choice and open-ended questions
Bingo - Task completion events with progress tracking

Key Features:
Admin Commands:

!create_event - Interactive event creation via DM
!start_event <id> - Start events
!list_events - View all events

User Commands:

!join_event <id> - Join events
!link_osrs <username> - Link OSRS accounts
!start_<challenge_name> - Begin challenges
!end_<challenge_name> - Complete challenges
!complete_bingo <task_number> - Mark bingo tasks complete
!leaderboard <id> - View rankings

Automated Features:

Daily leaderboard posting
Challenge releases on schedule
Event end detection
Bingo reminders
Data persistence with backups

Technical Highlights:

Robust Data Management - JSON storage with automatic backups and validation
WiseOldMan Integration - Rate-limited API calls for XP/boss tracking
Interactive Setup - DM-based event creation wizard
Error Handling - Comprehensive logging and graceful failures
Scalable Architecture - Modular design supporting multiple guilds

Setup Instructions:

Install: python setup.py (creates directories and files)
Dependencies: pip install -r requirements.txt
Configure: Add your Discord bot token to .env
Run: python enhanced_bot.py

Event Creation Flow:

Admin uses !create_event
Bot sends DM for interactive setup
Admin provides: name, duration, type, and type-specific details
Bot creates event and announces in designated channel
Users join with !join_event
Admin starts with !start_event

The bot handles all the complex scheduling, API interactions, and data management automatically. It's production-ready with proper error handling, logging, and data backup systems!
