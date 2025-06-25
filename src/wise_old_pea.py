"""
Wise Old Pea Bot - Main Entry Point
A Discord bot for running Old School RuneScape events with challenges, timing, and scoring.

This is the main orchestrator that coordinates all the specialized modules.
"""

import discord
from discord.ext import commands, tasks
import os
import datetime
import logging
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Import our custom modules
from database import Database
from event_manager import EventManager
from challenge_handlers import ChallengeHandlerFactory
from utils import is_event_ended

# Load environment variables
load_dotenv()

def setup_logging():
    """Setup comprehensive logging to files and console"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-15s | %(funcName)-20s | %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # File handler for all logs
    all_logs_handler = logging.FileHandler(
        logs_dir / f"wise_old_pea_{datetime.datetime.now().strftime('%Y%m%d')}.log", 
        encoding='utf-8'
    )
    all_logs_handler.setLevel(logging.DEBUG)
    all_logs_handler.setFormatter(detailed_formatter)
    
    # File handler for errors only
    error_handler = logging.FileHandler(
        logs_dir / f"errors_{datetime.datetime.now().strftime('%Y%m%d')}.log", 
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers
    root_logger.addHandler(all_logs_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Discord.py logger - reduce noise
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)
    
    return logging.getLogger('wise_old_pea')

# Setup logging
logger = setup_logging()

# Bot setup with all necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # This helps cache guild members
intents.presences = False  # We don't need this, keep it False for performance

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Initialize our core systems
database = Database()
event_manager = EventManager(bot, database)
challenge_factory = ChallengeHandlerFactory(bot, database)

@bot.event
async def on_ready():
    """Bot startup event - initialize everything"""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Connected to {len(bot.guilds)} guilds')
    
    for guild in bot.guilds:
        logger.info(f'  - {guild.name} (ID: {guild.id})')
    
    # Load command modules after bot is ready
    await load_command_modules()

    # Start background tasks
    check_timed_challenges.start()
    check_event_timing.start()
    check_peas_place_timers.start()
    
    logger.info("Background tasks started")
    logger.info("Wise Old Pea Bot is ready!")

async def load_command_modules():
    """
    Load command modules at the right time in the bot lifecycle
    This function handles the proper registration of all commands
    """
    try:
        logger.info("Loading command modules...")
        
        # Import the command modules - doing this here ensures all dependencies are ready
        from user_commands import UserCommands
        from admin_commands import AdminCommands
        
        # Create the command cog instances
        user_commands_cog = UserCommands(bot, database, event_manager)
        admin_commands_cog = AdminCommands(bot, database, event_manager)
        
        # Add the cogs to the bot (await if using discord.py 2.0+)
        try:
            # Try the async version first (discord.py 2.0+)
            await bot.add_cog(user_commands_cog)
            await bot.add_cog(admin_commands_cog)
            logger.info("Successfully loaded command modules (async method)")
        except TypeError:
            # Fall back to sync version (discord.py 1.x)
            bot.add_cog(user_commands_cog)
            bot.add_cog(admin_commands_cog)
            logger.info("Successfully loaded command modules (sync method)")
        
        # Log all registered commands for verification
        command_names = [cmd.name for cmd in bot.commands]
        logger.info(f"Registered commands: {', '.join(command_names)}")
        
    except Exception as e:
        logger.error(f"Failed to load command modules: {e}")
        logger.error(traceback.format_exc())
        # Don't exit - let the bot continue with just basic functionality

async def get_user_safely(user_id_str: str):
    """
    Safely get a Discord user by trying multiple methods
    Returns the user object if found, None otherwise
    """
    user_id = int(user_id_str)
    
    # Method 1: Check bot cache
    user = bot.get_user(user_id)
    if user:
        logger.debug(f"Found user {user_id} in bot cache")
        return user
    
    # Method 2: Try to fetch from Discord API
    try:
        user = await bot.fetch_user(user_id)
        if user:
            logger.debug(f"Fetched user {user_id} from Discord API")
            return user
    except Exception as e:
        logger.warning(f"Failed to fetch user {user_id} from API: {e}")
    
    # Method 3: Look through all guild members
    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if member:
            logger.debug(f"Found user {user_id} as member in guild {guild.name}")
            return member
    
    logger.error(f"Could not find user {user_id} through any method")
    return None


@bot.event
async def on_message(message):
    """
    Handle all incoming messages, including DMs for challenges
    This is where we route DM messages to the appropriate challenge handlers
    """
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Handle DM messages for active challenges
    if isinstance(message.channel, discord.DMChannel):
        await handle_dm_message(message)
    
    # Process regular commands
    await bot.process_commands(message)

async def handle_dm_message(message):
    """
    Handle DM messages for challenge interactions
    This routes messages to the appropriate challenge handler based on user's active challenge
    """
    user_id = str(message.author.id)
    active_event = database.get_active_event()
    
    if not active_event:
        logger.debug(f"No active event for DM from {message.author}")
        return
    
    # Check if event has ended
    event_data = database.get_event(active_event)
    if not event_data or is_event_ended(event_data.get('info', {})):
        await message.channel.send("❌ This event has concluded. DM interactions are no longer available.")
        return
    
    active_challenge_name = database.get_active_challenge(active_event, user_id)
    if not active_challenge_name:
        logger.debug(f"No active challenge for DM from {message.author}")
        return
    
    challenge_data = database.get_user_challenge_data(active_event, user_id, active_challenge_name)
    if challenge_data.get('status') != 'active':
        logger.debug(f"Challenge not active for DM from {message.author}: {challenge_data.get('status')}")
        return
    
    # Find the challenge object
    challenge = event_manager.get_challenge_by_name(active_challenge_name)
    if not challenge:
        logger.error(f"Could not find challenge object for {active_challenge_name}")
        return
    
    logger.info(f"Processing DM from {message.author} in challenge {challenge['display_name']}: {message.content[:50]}...")
    
    try:
        # Get the appropriate handler and process the message
        handler = challenge_factory.get_handler(challenge)
        handled = await handler.handle_dm_message(message, challenge, active_event, user_id)
        
        if not handled:
            logger.warning(f"DM message not handled for {message.author} in {challenge['display_name']}")
    
    except Exception as e:
        logger.error(f"Error handling DM from {message.author}: {e}")
        logger.error(traceback.format_exc())
        await message.channel.send("❌ An error occurred processing your message. Please contact an admin.")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for all commands"""
    logger.error(f"Command error in {ctx.command}: {error}")
    logger.error(f"Message content: '{ctx.message.content}'")
    logger.error(f"Author: {ctx.author} ({ctx.author.id})")
    logger.error(f"Channel: {ctx.channel}")
    logger.error(traceback.format_exc())
    
    # Handle different types of errors with user-friendly messages
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`. Use `!help {ctx.command}` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided. Use `!help {ctx.command}` for usage.")
    else:
        await ctx.send("❌ An error occurred while processing your command. Please check your input and try again.")

@bot.command(name='help')
async def help_command(ctx, *, command_name: str = None):
    """
    Custom help command with detailed information about all bot functionality
    Usage: !help [command_name]
    """
    logger.info(f"Help requested by {ctx.author} for command: {command_name}")
    
    if command_name:
        # Show help for specific command
        command = bot.get_command(command_name)
        if not command:
            await ctx.send(f"❌ Command `{command_name}` not found.")
            return
        
        embed = discord.Embed(
            title=f"📖 Help: !{command.name}",
            description=command.help or "No description available",
            color=0x0099ff
        )
        
        # Add usage information if available
        if hasattr(command, 'usage') and command.usage:
            embed.add_field(name="Usage", value=f"`!{command.name} {command.usage}`", inline=False)
        
        await ctx.send(embed=embed)
    else:
        # Show general help with all commands organized by category
        embed = discord.Embed(
            title="🎮 Wise Old Pea Bot - Help",
            description="A Discord bot for running Old School RuneScape events.",
            color=0xff9900
        )
        
        # Player commands
        player_commands = [
            ("link_account <osrs_username>", "Link your Discord account to your OSRS username"),
            ("join <challenge_name>", "Join a specific challenge using its name"),
            ("join <event_name>", "Join all challenges in an event.\n\t\tAvoids having to both !join and !start a challenge"),
            ("start <challenge_name>", "Begin your attempt at <challenge_name>, starting your timer and score counter."),
            ("finish <challenge_name>", "Finish a challenge, locking in your time."),
            ("evidence [challenge_name]", "Submit evidence of completion of a challenge (defaults to active/recent challenge)"),
            ("my_scores", "View your personal challenge scores"),
            ("skip", "Skip to next stage (Some DM-based challenges only)")
        ]
        
        player_text = "\n".join([f"`!{cmd}` - {desc}" for cmd, desc in player_commands])
        embed.add_field(name="👤 Player Commands", value=player_text, inline=False)
        
        # Admin commands
        admin_commands = [
            ("create_event", "Create a new event (opens DM setup)"),
            ("admin_scores [username]", "View all or specific user scores"),
            ("set_stage <username> <stage>", "Set user's challenge stage"),
            ("reset <username> <challenge>", "Reset user's challenge data"),
            ("event_status", "Check current event status and progress"),
            ("force_release", "Manually release the next challenge")
        ]
        
        admin_text = "\n".join([f"`!{cmd}` - {desc}" for cmd, desc in admin_commands])
        embed.add_field(name="🛡️ Admin Commands", value=admin_text, inline=False)


###################################################################################################
###################################################################################################
#        # How events work
#        embed.add_field(
#            name="🎯 How Events Work",
#            value="1. Admins create events with `!create_event`\n"
#                  "2. Players join with `!join <event_name>`\n"
#                  "3. Challenges are released automatically over time\n"
#                  "4. Players start challenges with `!start <challenge_name>`\n"
#                  "5. Some challenges happen in DMs, others in the channel\n"
#                  "6. Players submit evidence with `!evidence`\n"
#                  "7. Use `!my_scores` to track progress",
#            inline=False
#        )
###################################################################################################
###################################################################################################
         
        # Important notes
        embed.add_field(
            name="⚠️ Important Notes",
            value="• **Use exact challenge names from announcements for commands**\n"
                  "• You need to be able to receive Direct Messages from this bot\n"
                  "• Evidence submission is smart - it defaults to your current challenge",
            inline=False
        )
        
        await ctx.send(embed=embed)

# Background Tasks
# These run automatically to handle timing, releases, and timeouts

@tasks.loop(minutes=1)
async def check_timed_challenges():
    """
    Check for timed challenges that have expired
    This ensures users don't get stuck with challenges that should have timed out
    """
    try:
        timed_out_challenges = await event_manager.check_challenge_timeouts()
        
        if timed_out_challenges:
            logger.info(f"Processed {len(timed_out_challenges)} timed out challenges")
            
            # You could add notifications here if desired
            # for event_id, user_id, challenge_name in timed_out_challenges:
            #     # Notify user or admin about timeout
            #     pass
    
    except Exception as e:
        logger.error(f"Error in check_timed_challenges: {e}")
        logger.error(traceback.format_exc())

@tasks.loop(minutes=1)
async def check_event_timing():
    """
    Check for events that need new challenges released or status updates
    This handles the automatic challenge release schedule
    """
    try:
        updated_events = await event_manager.check_event_timing()
        
        if updated_events:
            logger.info(f"Updated {len(updated_events)} events")
    
    except Exception as e:
        logger.error(f"Error in check_event_timing: {e}")
        logger.error(traceback.format_exc())

@tasks.loop(minutes=1)
async def check_peas_place_timers():
    """Check for Pea's Place time delays and advance stages as needed"""
    current_time = datetime.datetime.now(datetime.UTC)
    
    try:
        active_event = database.get_active_event()
        if not active_event:
            return
        
        event_data = database.get_event(active_event)
        if not event_data or event_data.get('info', {}).get('status') != 'active':
            return
        
        # How long to wait between location hints
        TIME_DELAY_MINUTES = 5 # minutes
        
        peas_place_users = []  # Track for logging
        
        for user_id, user_data in event_data.get('users', {}).items():
            active_challenge = user_data.get('active_challenge')
            if active_challenge != 'peas_place':
                continue
            
            challenge_user_data = user_data.get(active_challenge, {})
            if challenge_user_data.get('status') != 'active':
                continue
            
            peas_place_users.append(user_id)
            
            # Get timing information
            last_stage_time = challenge_user_data.get('last_stage_time')
            if not last_stage_time:
                logger.warning(f"User {user_id} has no last_stage_time set")
                continue
            
            if isinstance(last_stage_time, str):
                last_stage_time = datetime.datetime.fromisoformat(last_stage_time.replace('Z', '+00:00'))
            
            # Calculate elapsed time
            elapsed_seconds = (current_time - last_stage_time).total_seconds()
            elapsed_minutes = elapsed_seconds / 60
            
            current_stage = challenge_user_data.get('stage', '1.1')
            
            logger.debug(f"Timer check for user {user_id}: stage={current_stage}, elapsed={elapsed_minutes:.1f}min, threshold={TIME_DELAY_MINUTES}min")
            
            if elapsed_minutes >= TIME_DELAY_MINUTES:
                logger.info(f"Timer threshold reached for user {user_id}: {elapsed_minutes:.1f} >= {TIME_DELAY_MINUTES} minutes")
                
                # Time to advance to next stage within same location
                user = await get_user_safely(user_id)
                
                if user:
                    challenge = event_manager.get_challenge_by_name('peas_place')
                    if challenge:
                        handler = challenge_factory.get_handler(challenge)
                        
                        # Use the new method to advance stage within location
                        advanced = await handler.advance_stage_within_location(user, challenge, active_event, user_id)
                        if advanced:
                            logger.info(f"Background task advanced Pea's Place stage for user {user_id}")
                        else:
                            logger.info(f"Background task could not advance stage for user {user_id} (probably at max stages for location)")
                    else:
                        logger.error(f"Could not find peas_place challenge")
                else:
                    logger.error(f"Could not find Discord user for ID {user_id} through any method")
        
        if peas_place_users:
            logger.debug(f"Checked Pea's Place timers for {len(peas_place_users)} users: {peas_place_users}")
        
    except Exception as e:
        logger.error(f"Error in check_peas_place_timers: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Wait for bot to be ready before starting loops
@check_timed_challenges.before_loop
@check_event_timing.before_loop  
@check_peas_place_timers.before_loop
async def before_loops():
    await bot.wait_until_ready()

def main():
    """Main entry point for the bot"""
    print("🎮 Starting Wise Old Pea Bot...")
    print("📋 Startup checklist:")
    print("  1. Set your bot token as environment variable: DISCORD_BOT_TOKEN")
    print("  2. Place challenge_rules.json in the same directory")
    print("  3. Invite the bot to your server with appropriate permissions")
    print("  4. Ensure the bot has permission to send DMs to users")
    
    # Check for required files
    if not Path('challenge_rules.json').exists():
        print("❌ Error: challenge_rules.json not found!")
        return
    
    # Get bot token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ Error: Please set the DISCORD_BOT_TOKEN environment variable")
        return
    
    # Start the bot
    try:
        logger.info("Starting bot with comprehensive logging enabled")
        print("🚀 Bot is starting up...")
        bot.run(token)
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == "__main__":
    main()