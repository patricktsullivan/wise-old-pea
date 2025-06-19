#!/usr/bin/env python3
"""
Enhanced Discord Events Bot with WiseOldMan Integration
Supports multiple event types: Multiple Challenges, Experience Gained, Bosses Killed, Trivia, and Bingo

Usage:
    python enhanced_bot.py

Commands:
    !create_event - Create a new event (Admin only)
    !start_event <event_id> - Start an event (Admin only)
    !join_event <event_id> - Join an event
    !list_events - List all events
    !event_info <event_id> - Get event information
    !link_osrs <username> - Link your OSRS account
    !leaderboard <event_id> - Show event leaderboard
    !start_<challenge_name> - Start a challenge
    !end_<challenge_name> - End a challenge
"""

import discord
from discord.ext import commands, tasks
import asyncio
import json
import datetime
import uuid
import aiohttp
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EventType(Enum):
    MULTIPLE_CHALLENGES = "multiple_challenges"
    EXPERIENCE_GAINED = "experience_gained"
    BOSSES_KILLED = "bosses_killed"
    TRIVIA = "trivia"
    BINGO = "bingo"

class EventStatus(Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

@dataclass
class OSRSAccount:
    discord_id: int
    username: str
    verified: bool = False
    linked_date: datetime.datetime = field(default_factory=datetime.datetime.now)

@dataclass
class Challenge:
    id: str
    name: str
    description: str
    event_id: str
    challenge_type: str
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    participants: Dict[int, datetime.datetime] = field(default_factory=dict)
    completions: Dict[int, datetime.datetime] = field(default_factory=dict)
    results: Dict[int, Any] = field(default_factory=dict)
    duration: int = 24  # hours

@dataclass
class TriviaQuestion:
    question: str
    choices: Optional[List[str]] = None
    correct_answers: Optional[List[str]] = None
    is_open_ended: bool = False
    explanation: Optional[str] = None

@dataclass
class BingoTask:
    id: str
    description: str
    completed_by: List[int] = field(default_factory=list)
    points: int = 1

@dataclass
class Event:
    id: str
    name: str
    event_type: EventType
    creator_id: int
    guild_id: int
    channel_id: Optional[int] = None
    duration: int = 24  # hours
    status: EventStatus = EventStatus.CREATED
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    participants: List[int] = field(default_factory=list)
    challenges: List[Challenge] = field(default_factory=list)
    trivia_questions: List[TriviaQuestion] = field(default_factory=list)
    bingo_tasks: List[BingoTask] = field(default_factory=list)
    challenge_interval: Optional[int] = None  # hours
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        # Convert datetime objects to ISO strings
        if result['start_time']:
            result['start_time'] = self.start_time.isoformat()
        if result['end_time']:
            result['end_time'] = self.end_time.isoformat()
        result['event_type'] = self.event_type.value
        result['status'] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Event from dictionary"""
        # Convert ISO strings back to datetime
        if data.get('start_time'):
            data['start_time'] = datetime.datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            data['end_time'] = datetime.datetime.fromisoformat(data['end_time'])
        
        # Convert enum strings back to enums
        data['event_type'] = EventType(data['event_type'])
        data['status'] = EventStatus(data.get('status', 'created'))
        
        # Reconstruct nested objects
        challenges = []
        for challenge_data in data.get('challenges', []):
            if challenge_data.get('start_time'):
                challenge_data['start_time'] = datetime.datetime.fromisoformat(challenge_data['start_time'])
            if challenge_data.get('end_time'):
                challenge_data['end_time'] = datetime.datetime.fromisoformat(challenge_data['end_time'])
            challenges.append(Challenge(**challenge_data))
        data['challenges'] = challenges
        
        trivia_questions = []
        for question_data in data.get('trivia_questions', []):
            trivia_questions.append(TriviaQuestion(**question_data))
        data['trivia_questions'] = trivia_questions
        
        bingo_tasks = []
        for task_data in data.get('bingo_tasks', []):
            bingo_tasks.append(BingoTask(**task_data))
        data['bingo_tasks'] = bingo_tasks
        
        return cls(**data)

class WiseOldManAPI:
    """Enhanced WiseOldMan API wrapper with error handling and rate limiting"""
    
    def __init__(self):
        self.base_url = "https://api.wiseoldman.net/v2"
        self.session = None
        self.rate_limit_delay = 1.0  # seconds between requests
        self.last_request_time = 0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Discord Events Bot'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make rate-limited API request"""
        if not self.session:
            raise RuntimeError("API session not initialized")
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
        
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.warning(f"Player not found: {endpoint}")
                    return None
                elif response.status == 429:
                    logger.warning("Rate limited by WiseOldMan API")
                    await asyncio.sleep(5)
                    return await self._make_request(endpoint, params)
                else:
                    logger.error(f"API request failed: {response.status} - {endpoint}")
                    return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None
    
    async def get_player(self, username: str) -> Optional[dict]:
        """Get player data"""
        return await self._make_request(f"players/{username}")
    
    async def get_player_gains(self, username: str, period: str = "1d") -> Optional[dict]:
        """Get player gains for specified period"""
        return await self._make_request(f"players/{username}/gained", {"period": period})
    
    async def get_player_records(self, username: str, metric: str = None) -> Optional[dict]:
        """Get player records"""
        params = {"metric": metric} if metric else None
        return await self._make_request(f"players/{username}/records", params)

class EventsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description="Advanced Discord bot for running video game events",
            help_command=commands.DefaultHelpCommand()
        )
        
        # Data storage
        self.events: Dict[str, Event] = {}
        self.osrs_accounts: Dict[int, OSRSAccount] = {}
        self.active_challenges: Dict[str, Dict[int, datetime.datetime]] = {}
        self.trivia_sessions: Dict[int, Dict[str, Any]] = {}
        self.pending_event_creation: Dict[int, Dict[str, Any]] = {}
        
        # Load data
        self.load_data()
        
    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("Setting up bot...")
        self.event_scheduler.start()
        self.daily_leaderboard_task.start()
        logger.info("Event scheduler started")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} connected to Discord!')
        logger.info(f'Guilds: {len(self.guilds)}')
        logger.info(f'Events loaded: {len(self.events)}')
    
    async def on_error(self, event, *args, **kwargs):
        """Handle errors"""
        logger.error(f"Error in {event}: {args}", exc_info=True)
    
    def save_data(self):
        """Save all data to files"""
        try:
            # Save events
            events_data = {}
            for event_id, event in self.events.items():
                events_data[event_id] = event.to_dict()
            
            with open('data/events.json', 'w') as f:
                json.dump(events_data, f, indent=2, default=str)
            
            # Save OSRS accounts
            accounts_data = {}
            for discord_id, account in self.osrs_accounts.items():
                accounts_data[str(discord_id)] = asdict(account)
            
            with open('data/osrs_accounts.json', 'w') as f:
                json.dump(accounts_data, f, indent=2, default=str)
            
            logger.debug("Data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def load_data(self):
        """Load data from files"""
        try:
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            
            # Load events
            try:
                with open('data/events.json', 'r') as f:
                    events_data = json.load(f)
                
                for event_id, event_dict in events_data.items():
                    self.events[event_id] = Event.from_dict(event_dict)
                
                logger.info(f"Loaded {len(self.events)} events")
                
            except FileNotFoundError:
                logger.info("No events file found, starting fresh")
            
            # Load OSRS accounts
            try:
                with open('data/osrs_accounts.json', 'r') as f:
                    accounts_data = json.load(f)
                
                for discord_id, account_dict in accounts_data.items():
                    if account_dict.get('linked_date'):
                        account_dict['linked_date'] = datetime.datetime.fromisoformat(account_dict['linked_date'])
                    self.osrs_accounts[int(discord_id)] = OSRSAccount(**account_dict)
                
                logger.info(f"Loaded {len(self.osrs_accounts)} OSRS accounts")
                
            except FileNotFoundError:
                logger.info("No OSRS accounts file found, starting fresh")
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    # Event Creation Commands
    @commands.command(name='create_event')
    @commands.has_permissions(administrator=True)
    async def create_event(self, ctx):
        """Create a new event - Admin only"""
        user_id = ctx.author.id
        
        self.pending_event_creation[user_id] = {
            'step': 'event_name',
            'guild_id': ctx.guild.id,
            'channel_id': ctx.channel.id
        }
        
        try:
            embed = discord.Embed(
                title="🎉 Event Creation Started",
                description="I've sent you a DM to continue the setup process!",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
            await ctx.author.send(
                "Let's create a new event! What would you like to name this event?\n"
                "*You can cancel at any time by typing 'cancel'*"
            )
        except discord.Forbidden:
            await ctx.send("❌ I couldn't send you a DM. Please enable DMs from server members.")
            del self.pending_event_creation[user_id]
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle DM messages for event creation"""
        if message.author.bot:
            return
        
        # Handle DM messages for event creation
        if isinstance(message.channel, discord.DMChannel):
            await self.handle_event_creation_dm(message)
        
        # Handle trivia responses
        if message.author.id in self.trivia_sessions:
            await self.handle_trivia_response(message)
        
        # Handle challenge commands
        if message.content.startswith('!start_') or message.content.startswith('!end_'):
            await self.handle_challenge_command(message)
        
        await self.process_commands(message)
    
    async def handle_challenge_command(self, message):
        """Handle challenge start/end commands"""
        command_parts = message.content.split('_', 1)
        if len(command_parts) < 2:
            return
        
        action = command_parts[0][1:]  # Remove !
        challenge_name = command_parts[1]
        
        # Find the challenge
        challenge = None
        event = None
        for event_obj in self.events.values():
            for chall in event_obj.challenges:
                if chall.name.lower().replace(' ', '_') == challenge_name.lower():
                    challenge = chall
                    event = event_obj
                    break
            if challenge:
                break
        
        if not challenge:
            await message.channel.send(f"❌ Challenge '{challenge_name}' not found.")
            return
        
        if action == 'start':
            await self.start_challenge_for_user(message.author, challenge, event, message.channel)
        elif action == 'end':
            await self.end_challenge_for_user(message.author, challenge, event, message.channel)
    
    async def start_challenge_for_user(self, user, challenge, event, channel):
        """Start a challenge for a user"""
        if user.id not in event.participants:
            await channel.send("❌ You must join the event first using `!join_event <event_id>`")
            return
        
        if user.id in challenge.participants:
            await channel.send("❌ You have already started this challenge!")
            return
        
        challenge.participants[user.id] = datetime.datetime.now()
        self.save_data()
        
        embed = discord.Embed(
            title="🚀 Challenge Started!",
            description=f"**{challenge.name}**\n\n{challenge.description}",
            color=discord.Color.green()
        )
        embed.add_field(name="Started At", value=challenge.participants[user.id].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.set_footer(text=f"Use !end_{challenge.name.lower().replace(' ', '_')} when complete")
        
        await channel.send(embed=embed)
        
        # If it's a trivia challenge, start the trivia session
        if challenge.challenge_type == "trivia":
            await self.start_trivia_session(user, challenge, event)
    
    async def end_challenge_for_user(self, user, challenge, event, channel):
        """End a challenge for a user"""
        if user.id not in challenge.participants:
            await channel.send("❌ You haven't started this challenge yet!")
            return
        
        if user.id in challenge.completions:
            await channel.send("❌ You have already completed this challenge!")
            return
        
        end_time = datetime.datetime.now()
        start_time = challenge.participants[user.id]
        duration = end_time - start_time
        
        challenge.completions[user.id] = end_time
        
        # Calculate results based on challenge type
        if challenge.challenge_type in ["experience_gained", "bosses_killed"]:
            await self.calculate_wom_results(user, challenge, event, start_time, end_time)
        
        self.save_data()
        
        embed = discord.Embed(
            title="🎯 Challenge Completed!",
            description=f"**{challenge.name}**",
            color=discord.Color.gold()
        )
        embed.add_field(name="Duration", value=str(duration).split('.')[0], inline=True)
        embed.add_field(name="Completed At", value=end_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        await channel.send(embed=embed)
    
    async def calculate_wom_results(self, user, challenge, event, start_time, end_time):
        """Calculate WiseOldMan results for a challenge"""
        if user.id not in self.osrs_accounts:
            return
        
        username = self.osrs_accounts[user.id].username
        
        try:
            async with WiseOldManAPI() as api:
                # Calculate the period for the challenge duration
                duration_hours = (end_time - start_time).total_seconds() / 3600
                
                if duration_hours <= 24:
                    period = "1d"
                elif duration_hours <= 168:  # 7 days
                    period = "7d"
                else:
                    period = "1m"
                
                gains = await api.get_player_gains(username, period)
                
                if gains:
                    if challenge.challenge_type == "experience_gained":
                        total_xp = gains.get('data', {}).get('overall', {}).get('experience', {}).get('gained', 0)
                        challenge.results[user.id] = {'total_xp': total_xp, 'gains': gains}
                    elif challenge.challenge_type == "bosses_killed":
                        boss_kills = {}
                        for boss, data in gains.get('data', {}).items():
                            if 'kills' in data and data['kills'].get('gained', 0) > 0:
                                boss_kills[boss] = data['kills']['gained']
                        challenge.results[user.id] = {'boss_kills': boss_kills, 'gains': gains}
                        
        except Exception as e:
            logger.error(f"Error calculating WoM results: {e}")
    
    async def handle_event_creation_dm(self, message):
        """Handle event creation through DMs"""
        user_id = message.author.id
        
        if user_id not in self.pending_event_creation:
            return
        
        if message.content.lower() == 'cancel':
            del self.pending_event_creation[user_id]
            await message.channel.send("❌ Event creation cancelled.")
            return
        
        session = self.pending_event_creation[user_id]
        step = session['step']
        
        try:
            if step == 'event_name':
                session['event_name'] = message.content
                session['step'] = 'event_duration'
                await message.channel.send(
                    "Great! How long should this event last?\n"
                    "Please specify in hours (e.g., 24 for 1 day, 168 for 1 week)"
                )
            
            elif step == 'event_duration':
                duration = int(message.content)
                if duration < 1 or duration > 168:  # Max 1 week
                    await message.channel.send("❌ Duration must be between 1 and 168 hours (1 week).")
                    return
                
                session['event_duration'] = duration
                session['step'] = 'event_type'
                
                embed = discord.Embed(
                    title="Select Event Type",
                    description="Choose the type of event you want to create:",
                    color=discord.Color.blue()
                )
                embed.add_field(name="1️⃣ Multiple Challenges", value="Series of timed challenges", inline=False)
                embed.add_field(name="2️⃣ Experience Gained", value="Track XP gains via WiseOldMan", inline=False)
                embed.add_field(name="3️⃣ Bosses Killed", value="Track boss kill counts", inline=False)
                embed.add_field(name="4️⃣ Trivia", value="Question and answer challenges", inline=False)
                embed.add_field(name="5️⃣ Bingo", value="Complete various tasks", inline=False)
                embed.set_footer(text="Reply with the number (1-5)")
                
                await message.channel.send(embed=embed)
            
            elif step == 'event_type':
                type_mapping = {
                    '1': EventType.MULTIPLE_CHALLENGES,
                    '2': EventType.EXPERIENCE_GAINED,
                    '3': EventType.BOSSES_KILLED,
                    '4': EventType.TRIVIA,
                    '5': EventType.BINGO
                }
                
                if message.content not in type_mapping:
                    await message.channel.send("❌ Please enter a valid option (1-5).")
                    return
                
                event_type = type_mapping[message.content]
                session['event_type'] = event_type
                
                if event_type == EventType.MULTIPLE_CHALLENGES:
                    session['step'] = 'challenge_interval'
                    await message.channel.send(
                        "How often should new challenges be released?\n"
                        "Please specify in hours (minimum 1 hour)"
                    )
                elif event_type == EventType.TRIVIA:
                    session['step'] = 'trivia_questions'
                    session['trivia_questions'] = []
                    await message.channel.send(
                        "Let's add trivia questions!\n"
                        "Please provide a question (or type 'done' when finished):"
                    )
                elif event_type == EventType.BINGO:
                    session['step'] = 'bingo_tasks'
                    session['bingo_tasks'] = []
                    await message.channel.send(
                        "Let's add bingo tasks!\n"
                        "Please provide a task description (or type 'done' when finished):"
                    )
                else:
                    await self.finalize_event_creation(message, session)
            
            elif step == 'challenge_interval':
                interval = int(message.content)
                if interval < 1:
                    await message.channel.send("❌ Challenge interval must be at least 1 hour.")
                    return
                
                session['challenge_interval'] = interval
                session['step'] = 'challenge_creation'
                session['challenges'] = []
                await message.channel.send(
                    "Now let's create challenges for your event!\n"
                    "Please provide a challenge name (or type 'done' when finished):"
                )
            
            elif step == 'challenge_creation':
                await self.handle_challenge_creation(message, session)
            
            elif step == 'trivia_questions':
                await self.handle_trivia_creation(message, session)
            
            elif step == 'bingo_tasks':
                await self.handle_bingo_creation(message, session)
                
        except ValueError:
            await message.channel.send("❌ Please enter a valid number.")
        except Exception as e:
            logger.error(f"Error in event creation: {e}")
            await message.channel.send("❌ An error occurred. Please try again.")
    
    async def handle_challenge_creation(self, message, session):
        """Handle challenge creation for multiple challenges event"""
        if message.content.lower() == 'done':
            if not session.get('challenges'):
                await message.channel.send("❌ You must create at least one challenge!")
                return
            await self.finalize_event_creation(message, session)
            return
        
        # Create new challenge
        challenge_name = message.content
        challenge_id = str(uuid.uuid4())[:8]
        
        session['current_challenge'] = {
            'id': challenge_id,
            'name': challenge_name,
            'step': 'description'
        }
        
        await message.channel.send(f"Great! Now provide a description for '{challenge_name}':")
    
    async def handle_trivia_creation(self, message, session):
        """Handle trivia question creation"""
        if message.content.lower() == 'done':
            if not session.get('trivia_questions'):
                await message.channel.send("❌ You must create at least one trivia question!")
                return
            await self.finalize_event_creation(message, session)
            return
        
        if 'current_question' not in session:
            # New question
            session['current_question'] = {
                'question': message.content,
                'step': 'choices'
            }
            await message.channel.send(
                "Do you want this to be multiple choice? If yes, provide the choices separated by commas.\n"
                "If no, just type 'open' for an open-ended question:"
            )
        else:
            current_q = session['current_question']
            
            if current_q['step'] == 'choices':
                if message.content.lower() == 'open':
                    # Open-ended question
                    question = TriviaQuestion(
                        question=current_q['question'],
                        is_open_ended=True
                    )
                    session['trivia_questions'].append(question)
                    del session['current_question']
                    await message.channel.send(
                        f"Question added! Total questions: {len(session['trivia_questions'])}\n"
                        "Add another question or type 'done' to finish:"
                    )
                else:
                    # Multiple choice
                    choices = [choice.strip() for choice in message.content.split(',')]
                    current_q['choices'] = choices
                    current_q['step'] = 'correct_answer'
                    
                    choices_text = '\n'.join([f"{i+1}. {choice}" for i, choice in enumerate(choices)])
                    await message.channel.send(
                        f"Choices:\n{choices_text}\n\n"
                        "Which choice(s) are correct? (Enter numbers separated by commas, e.g., '1,3'):"
                    )
            
            elif current_q['step'] == 'correct_answer':
                try:
                    correct_indices = [int(x.strip()) - 1 for x in message.content.split(',')]
                    correct_answers = [current_q['choices'][i] for i in correct_indices]
                    
                    question = TriviaQuestion(
                        question=current_q['question'],
                        choices=current_q['choices'],
                        correct_answers=correct_answers,
                        is_open_ended=False
                    )
                    session['trivia_questions'].append(question)
                    del session['current_question']
                    
                    await message.channel.send(
                        f"Question added! Total questions: {len(session['trivia_questions'])}\n"
                        "Add another question or type 'done' to finish:"
                    )
                except (ValueError, IndexError):
                    await message.channel.send("❌ Invalid choice numbers. Please try again:")
    
    async def handle_bingo_creation(self, message, session):
        """Handle bingo task creation"""
        if message.content.lower() == 'done':
            if not session.get('bingo_tasks'):
                await message.channel.send("❌ You must create at least one bingo task!")
                return
            await self.finalize_event_creation(message, session)
            return
        
        # Add bingo task
        task_id = str(uuid.uuid4())[:8]
        task = BingoTask(id=task_id, description=message.content)
        session['bingo_tasks'].append(task)
        
        await message.channel.send(
            f"Task added! Total tasks: {len(session['bingo_tasks'])}\n"
            "Add another task or type 'done' to finish:"
        )
    
    async def finalize_event_creation(self, message, session):
        """Finalize event creation"""
        event_id = str(uuid.uuid4())[:8]
        
        event = Event(
            id=event_id,
            name=session['event_name'],
            event_type=session['event_type'],
            creator_id=message.author.id,
            guild_id=session['guild_id'],
            channel_id=session['channel_id'],
            duration=session['event_duration'],
            challenge_interval=session.get('challenge_interval')
        )
        
        # Add challenges, trivia questions, or bingo tasks
        if session['event_type'] == EventType.MULTIPLE_CHALLENGES:
            for challenge_data in session.get('challenges', []):
                challenge = Challenge(
                    id=challenge_data['id'],
                    name=challenge_data['name'],
                    description=challenge_data['description'],
                    event_id=event_id,
                    challenge_type="general"
                )
                event.challenges.append(challenge)
        
        elif session['event_type'] == EventType.TRIVIA:
            event.trivia_questions = session.get('trivia_questions', [])
        
        elif session['event_type'] == EventType.BINGO:
            event.bingo_tasks = session.get('bingo_tasks', [])
        
        # Save event
        self.events[event_id] = event
        self.save_data()
        
        # Clean up session
        del self.pending_event_creation[message.author.id]
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ Event Created Successfully!",
            description=f"**{event.name}** has been created with ID: `{event_id}`",
            color=discord.Color.green()
        )
        embed.add_field(name="Type", value=event.event_type.value.replace('_', ' ').title(), inline=True)
        embed.add_field(name="Duration", value=f"{event.duration} hours", inline=True)
        
        if event.event_type == EventType.MULTIPLE_CHALLENGES:
            embed.add_field(name="Challenge Interval", value=f"{event.challenge_interval} hours", inline=True)
            embed.add_field(name="Challenges", value=str(len(event.challenges)), inline=True)
        elif event.event_type == EventType.TRIVIA:
            embed.add_field(name="Questions", value=str(len(event.trivia_questions)), inline=True)
        elif event.event_type == EventType.BINGO:
            embed.add_field(name="Tasks", value=str(len(event.bingo_tasks)), inline=True)
        
        embed.set_footer(text=f"Use !start_event {event_id} to begin the event")
        
        await message.channel.send(embed=embed)
        
        # Also send to the designated channel
        try:
            guild = self.get_guild(event.guild_id)
            channel = guild.get_channel(event.channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Could not send to designated channel: {e}")
    
    # Event Management Commands
    @commands.command(name='start_event')
    @commands.has_permissions(administrator=True)
    async def start_event(self, ctx, event_id: str):
        """Start an event - Admin only"""
        if event_id not in self.events:
            await ctx.send("❌ Event not found!")
            return
        
        event = self.events[event_id]
        
        if event.status != EventStatus.CREATED:
            await ctx.send("❌ Event has already been started!")
            return
        
        # Start the event
        event.status = EventStatus.ACTIVE
        event.start_time = datetime.datetime.now()
        event.end_time = event.start_time + datetime.timedelta(hours=event.duration)
        
        self.save_data()
        
        embed = discord.Embed(
            title="🚀 Event Started!",
            description=f"**{event.name}** is now active!",
            color=discord.Color.green()
        )
        embed.add_field(name="Event ID", value=event_id, inline=True)
        embed.add_field(name="Duration", value=f"{event.duration} hours", inline=True)
        embed.add_field(name="Ends At", value=event.end_time.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
        embed.set_footer(text=f"Use !join_event {event_id} to participate!")
        
        await ctx.send(embed=embed)
        
        # Handle different event types
        if event.event_type == EventType.BINGO:
            await self.announce_bingo_tasks(ctx.channel, event)
        elif event.event_type == EventType.MULTIPLE_CHALLENGES:
            await self.schedule_first_challenge(event)
    
    @commands.command(name='join_event')
    async def join_event(self, ctx, event_id: str):
        """Join an event"""
        if event_id not in self.events:
            await ctx.send("❌ Event not found!")
            return
        
        event = self.events[event_id]
        
        if event.status != EventStatus.ACTIVE:
            await ctx.send("❌ Event is not currently active!")
            return
        
        if ctx.author.id in event.participants:
            await ctx.send("❌ You are already participating in this event!")
            return
        
        event.participants.append(ctx.author.id)
        self.save_data()
        
        embed = discord.Embed(
            title="✅ Joined Event!",
            description=f"You have successfully joined **{event.name}**!",
            color=discord.Color.green()
        )
        
        # Add event-specific instructions
        if event.event_type == EventType.EXPERIENCE_GAINED or event.event_type == EventType.BOSSES_KILLED:
            if ctx.author.id not in self.osrs_accounts:
                embed.add_field(
                    name="⚠️ OSRS Account Required",
                    value="Use `!link_osrs <username>` to link your account for tracking!",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='list_events')
    async def list_events(self, ctx):
        """List all events"""
        if not self.events:
            await ctx.send("No events found!")
            return
        
        embed = discord.Embed(
            title="📅 Events List",
            color=discord.Color.blue()
        )
        
        for event_id, event in self.events.items():
            status_emoji = {
                EventStatus.CREATED: "⏸️",
                EventStatus.ACTIVE: "🟢",
                EventStatus.PAUSED: "⏸️",
                EventStatus.COMPLETED: "✅"
            }
            
            embed.add_field(
                name=f"{status_emoji[event.status]} {event.name}",
                value=f"ID: `{event_id}`\nType: {event.event_type.value.replace('_', ' ').title()}\nParticipants: {len(event.participants)}",
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='event_info')
    async def event_info(self, ctx, event_id: str):
        """Get detailed event information"""
        if event_id not in self.events:
            await ctx.send("❌ Event not found!")
            return
        
        event = self.events[event_id]
        
        embed = discord.Embed(
            title=f"📋 {event.name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Event ID", value=event_id, inline=True)
        embed.add_field(name="Type", value=event.event_type.value.replace('_', ' ').title(), inline=True)
        embed.add_field(name="Status", value=event.status.value.title(), inline=True)
        embed.add_field(name="Duration", value=f"{event.duration} hours", inline=True)
        embed.add_field(name="Participants", value=str(len(event.participants)), inline=True)
        
        if event.start_time:
            embed.add_field(name="Started", value=event.start_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if event.end_time:
            embed.add_field(name="Ends", value=event.end_time.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if event.event_type == EventType.MULTIPLE_CHALLENGES:
            embed.add_field(name="Challenge Interval", value=f"{event.challenge_interval} hours", inline=True)
            embed.add_field(name="Total Challenges", value=str(len(event.challenges)), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='link_osrs')
    async def link_osrs(self, ctx, username: str):
        """Link your OSRS account"""
        # Verify the account exists
        async with WiseOldManAPI() as api:
            player_data = await api.get_player(username)
            
            if not player_data:
                await ctx.send("❌ OSRS account not found on WiseOldMan. Make sure the username is correct and the account is tracked.")
                return
        
        # Link the account
        account = OSRSAccount(
            discord_id=ctx.author.id,
            username=username,
            verified=True
        )
        
        self.osrs_accounts[ctx.author.id] = account
        self.save_data()
        
        embed = discord.Embed(
            title="✅ OSRS Account Linked!",
            description=f"Successfully linked OSRS account: **{username}**",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx, event_id: str):
        """Show event leaderboard"""
        if event_id not in self.events:
            await ctx.send("❌ Event not found!")
            return
        
        event = self.events[event_id]
        
        if not event.participants:
            await ctx.send("❌ No participants in this event yet!")
            return
        
        await self.generate_leaderboard(ctx.channel, event)
    
    async def generate_leaderboard(self, channel, event):
        """Generate and send leaderboard for an event"""
        embed = discord.Embed(
            title=f"🏆 {event.name} - Leaderboard",
            color=discord.Color.gold()
        )
        
        if event.event_type == EventType.EXPERIENCE_GAINED:
            await self.generate_xp_leaderboard(embed, event)
        elif event.event_type == EventType.BOSSES_KILLED:
            await self.generate_boss_leaderboard(embed, event)
        elif event.event_type == EventType.TRIVIA:
            await self.generate_trivia_leaderboard(embed, event)
        elif event.event_type == EventType.BINGO:
            await self.generate_bingo_leaderboard(embed, event)
        elif event.event_type == EventType.MULTIPLE_CHALLENGES:
            await self.generate_challenges_leaderboard(embed, event)
        
        await channel.send(embed=embed)
    
    async def generate_xp_leaderboard(self, embed, event):
        """Generate XP gains leaderboard"""
        participants_data = []
        
        for user_id in event.participants:
            if user_id in self.osrs_accounts:
                username = self.osrs_accounts[user_id].username
                
                # Get total XP from all completed challenges
                total_xp = 0
                for challenge in event.challenges:
                    if user_id in challenge.results:
                        total_xp += challenge.results[user_id].get('total_xp', 0)
                
                participants_data.append((user_id, username, total_xp))
        
        # Sort by XP
        participants_data.sort(key=lambda x: x[2], reverse=True)
        
        if not participants_data:
            embed.add_field(name="No Data", value="No XP data available yet", inline=False)
            return
        
        leaderboard_text = ""
        for i, (user_id, username, xp) in enumerate(participants_data[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            leaderboard_text += f"{medal} **{username}** - {xp:,} XP\n"
        
        embed.add_field(name="Top Participants", value=leaderboard_text, inline=False)
    
    async def generate_boss_leaderboard(self, embed, event):
        """Generate boss kills leaderboard"""
        participants_data = []
        
        for user_id in event.participants:
            if user_id in self.osrs_accounts:
                username = self.osrs_accounts[user_id].username
                
                # Get total boss kills from all completed challenges
                total_kills = 0
                for challenge in event.challenges:
                    if user_id in challenge.results:
                        boss_kills = challenge.results[user_id].get('boss_kills', {})
                        total_kills += sum(boss_kills.values())
                
                participants_data.append((user_id, username, total_kills))
        
        # Sort by kills
        participants_data.sort(key=lambda x: x[2], reverse=True)
        
        if not participants_data:
            embed.add_field(name="No Data", value="No boss kill data available yet", inline=False)
            return
        
        leaderboard_text = ""
        for i, (user_id, username, kills) in enumerate(participants_data[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            leaderboard_text += f"{medal} **{username}** - {kills:,} kills\n"
        
        embed.add_field(name="Top Participants", value=leaderboard_text, inline=False)
    
    async def generate_trivia_leaderboard(self, embed, event):
        """Generate trivia leaderboard"""
        # This would track scores from trivia sessions
        embed.add_field(name="Trivia Scores", value="Trivia leaderboard coming soon!", inline=False)
    
    async def generate_bingo_leaderboard(self, embed, event):
        """Generate bingo leaderboard"""
        participants_data = []
        
        for user_id in event.participants:
            completed_tasks = 0
            for task in event.bingo_tasks:
                if user_id in task.completed_by:
                    completed_tasks += 1
            
            if completed_tasks > 0:
                user = self.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                participants_data.append((user_id, username, completed_tasks))
        
        # Sort by completed tasks
        participants_data.sort(key=lambda x: x[2], reverse=True)
        
        if not participants_data:
            embed.add_field(name="No Completions", value="No bingo tasks completed yet", inline=False)
            return
        
        leaderboard_text = ""
        for i, (user_id, username, tasks) in enumerate(participants_data[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            leaderboard_text += f"{medal} **{username}** - {tasks}/{len(event.bingo_tasks)} tasks\n"
        
        embed.add_field(name="Top Participants", value=leaderboard_text, inline=False)
    
    async def generate_challenges_leaderboard(self, embed, event):
        """Generate multiple challenges leaderboard"""
        participants_data = []
        
        for user_id in event.participants:
            completed_challenges = 0
            for challenge in event.challenges:
                if user_id in challenge.completions:
                    completed_challenges += 1
            
            if completed_challenges > 0:
                user = self.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                participants_data.append((user_id, username, completed_challenges))
        
        # Sort by completed challenges
        participants_data.sort(key=lambda x: x[2], reverse=True)
        
        if not participants_data:
            embed.add_field(name="No Completions", value="No challenges completed yet", inline=False)
            return
        
        leaderboard_text = ""
        for i, (user_id, username, challenges) in enumerate(participants_data[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            leaderboard_text += f"{medal} **{username}** - {challenges}/{len(event.challenges)} challenges\n"
        
        embed.add_field(name="Top Participants", value=leaderboard_text, inline=False)
    
    # Scheduled Tasks
    @tasks.loop(minutes=10)
    async def event_scheduler(self):
        """Check for events that need updates"""
        try:
            current_time = datetime.datetime.now()
            
            for event in self.events.values():
                if event.status == EventStatus.ACTIVE:
                    # Check if event should end
                    if current_time >= event.end_time:
                        await self.end_event(event)
                    
                    # Check for new challenges to release
                    elif event.event_type == EventType.MULTIPLE_CHALLENGES:
                        await self.check_challenge_releases(event, current_time)
                    
                    # Check for bingo announcements
                    elif event.event_type == EventType.BINGO:
                        await self.check_bingo_announcements(event, current_time)
                        
        except Exception as e:
            logger.error(f"Error in event scheduler: {e}")
    
    @tasks.loop(hours=24)
    async def daily_leaderboard_task(self):
        """Post daily leaderboards for active events"""
        try:
            for event in self.events.values():
                if event.status == EventStatus.ACTIVE:
                    guild = self.get_guild(event.guild_id)
                    if guild and event.channel_id:
                        channel = guild.get_channel(event.channel_id)
                        if channel:
                            await self.generate_leaderboard(channel, event)
        except Exception as e:
            logger.error(f"Error in daily leaderboard task: {e}")
    
    async def end_event(self, event):
        """End an event and post final results"""
        event.status = EventStatus.COMPLETED
        self.save_data()
        
        try:
            guild = self.get_guild(event.guild_id)
            if guild and event.channel_id:
                channel = guild.get_channel(event.channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🏁 Event Completed!",
                        description=f"**{event.name}** has ended!",
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed)
                    
                    # Post final leaderboard
                    await self.generate_leaderboard(channel, event)
        except Exception as e:
            logger.error(f"Error ending event: {e}")
    
    async def check_challenge_releases(self, event, current_time):
        """Check if new challenges should be released"""
        if not event.challenge_interval:
            return
        
        hours_since_start = (current_time - event.start_time).total_seconds() / 3600
        challenges_to_release = int(hours_since_start / event.challenge_interval) + 1
        
        # Release challenges that haven't been released yet
        for i, challenge in enumerate(event.challenges[:challenges_to_release]):
            if not challenge.start_time:
                await self.release_challenge(event, challenge)
    
    async def release_challenge(self, event, challenge):
        """Release a new challenge"""
        challenge.start_time = datetime.datetime.now()
        challenge.end_time = challenge.start_time + datetime.timedelta(hours=24)  # Default 24h duration
        self.save_data()
        
        try:
            guild = self.get_guild(event.guild_id)
            if guild and event.channel_id:
                channel = guild.get_channel(event.channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🆕 New Challenge Released!",
                        description=f"**{challenge.name}**\n\n{challenge.description}",
                        color=discord.Color.purple()
                    )
                    embed.add_field(
                        name="How to Participate",
                        value=f"Use `!start_{challenge.name.lower().replace(' ', '_')}` to begin!",
                        inline=False
                    )
                    embed.set_footer(text=f"Challenge ends in 24 hours")
                    
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error releasing challenge: {e}")
    
    async def schedule_first_challenge(self, event):
        """Schedule the first challenge for a multiple challenges event"""
        if event.challenges:
            await self.release_challenge(event, event.challenges[0])
    
    async def check_bingo_announcements(self, event, current_time):
        """Check if bingo announcements should be made"""
        time_remaining = (event.end_time - current_time).total_seconds() / 3600
        
        # Announce when 25% time remaining
        if 'quarter_warning' not in event.data and time_remaining <= event.duration * 0.25:
            event.data['quarter_warning'] = True
            await self.announce_bingo_reminder(event, "25% time remaining!")
        
        # Announce when 1 hour remaining
        elif 'hour_warning' not in event.data and time_remaining <= 1:
            event.data['hour_warning'] = True
            await self.announce_bingo_reminder(event, "1 hour remaining!")
    
    async def announce_bingo_tasks(self, channel, event):
        """Announce bingo tasks at event start"""
        embed = discord.Embed(
            title="🎯 Bingo Tasks",
            description="Complete as many tasks as possible during the event!",
            color=discord.Color.orange()
        )
        
        tasks_text = ""
        for i, task in enumerate(event.bingo_tasks, 1):
            tasks_text += f"{i}. {task.description}\n"
        
        embed.add_field(name="Tasks", value=tasks_text, inline=False)
        embed.set_footer(text="Use !complete_bingo <task_number> when you complete a task")
        
        await channel.send(embed=embed)
    
    async def announce_bingo_reminder(self, event, message):
        """Send bingo reminder"""
        try:
            guild = self.get_guild(event.guild_id)
            if guild and event.channel_id:
                channel = guild.get_channel(event.channel_id)
                if channel:
                    embed = discord.Embed(
                        title="⏰ Bingo Reminder",
                        description=message,
                        color=discord.Color.yellow()
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending bingo reminder: {e}")
    
    @commands.command(name='complete_bingo')
    async def complete_bingo(self, ctx, task_number: int):
        """Mark a bingo task as complete"""
        # Find the user's active bingo event
        user_event = None
        for event in self.events.values():
            if (event.status == EventStatus.ACTIVE and 
                event.event_type == EventType.BINGO and 
                ctx.author.id in event.participants):
                user_event = event
                break
        
        if not user_event:
            await ctx.send("❌ You're not participating in any active bingo events!")
            return
        
        if task_number < 1 or task_number > len(user_event.bingo_tasks):
            await ctx.send(f"❌ Invalid task number! Choose between 1 and {len(user_event.bingo_tasks)}")
            return
        
        task = user_event.bingo_tasks[task_number - 1]
        
        if ctx.author.id in task.completed_by:
            await ctx.send("❌ You have already completed this task!")
            return
        
        task.completed_by.append(ctx.author.id)
        self.save_data()
        
        embed = discord.Embed(
            title="✅ Bingo Task Completed!",
            description=f"**Task {task_number}:** {task.description}",
            color=discord.Color.green()
        )
        
        completed_count = sum(1 for t in user_event.bingo_tasks if ctx.author.id in t.completed_by)
        embed.add_field(
            name="Progress",
            value=f"{completed_count}/{len(user_event.bingo_tasks)} tasks completed",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    # Trivia handling
    async def start_trivia_session(self, user, challenge, event):
        """Start a trivia session for a user"""
        if not event.trivia_questions:
            return
        
        self.trivia_sessions[user.id] = {
            'event_id': event.id,
            'challenge_id': challenge.id,
            'questions': event.trivia_questions.copy(),
            'current_question': 0,
            'score': 0,
            'answers': []
        }
        
        await self.send_next_trivia_question(user)
    
    async def send_next_trivia_question(self, user):
        """Send the next trivia question to a user"""
        session = self.trivia_sessions[user.id]
        
        if session['current_question'] >= len(session['questions']):
            await self.end_trivia_session(user)
            return
        
        question = session['questions'][session['current_question']]
        
        embed = discord.Embed(
            title=f"❓ Question {session['current_question'] + 1}/{len(session['questions'])}",
            description=question.question,
            color=discord.Color.blue()
        )
        
        if not question.is_open_ended and question.choices:
            choices_text = '\n'.join([f"{i+1}. {choice}" for i, choice in enumerate(question.choices)])
            embed.add_field(name="Choices", value=choices_text, inline=False)
            embed.set_footer(text="Reply with the number of your choice")
        else:
            embed.set_footer(text="Reply with your answer")
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Could not send trivia question to {user.id}")
    
    async def handle_trivia_response(self, message):
        """Handle a trivia response from a user"""
        session = self.trivia_sessions[message.author.id]
        question = session['questions'][session['current_question']]
        
        # Store the answer
        session['answers'].append(message.content)
        
        # Check if correct (for multiple choice)
        if not question.is_open_ended:
            try:
                choice_num = int(message.content) - 1
                if 0 <= choice_num < len(question.choices):
                    user_answer = question.choices[choice_num]
                    if user_answer in question.correct_answers:
                        session['score'] += 1
                        await message.channel.send("✅ Correct!")
                    else:
                        correct_answers = ', '.join(question.correct_answers)
                        await message.channel.send(f"❌ Incorrect. The correct answer(s): {correct_answers}")
                else:
                    await message.channel.send("❌ Invalid choice number")
                    return
            except ValueError:
                await message.channel.send("❌ Please enter a valid number")
                return
        else:
            await message.channel.send("📝 Answer recorded!")
        
        # Move to next question
        session['current_question'] += 1
        await asyncio.sleep(2)  # Brief pause
        await self.send_next_trivia_question(message.author)
    
    async def end_trivia_session(self, user):
        """End a trivia session"""
        session = self.trivia_sessions[user.id]
        
        embed = discord.Embed(
            title="🎉 Trivia Completed!",
            description=f"You scored {session['score']}/{len(session['questions'])}!",
            color=discord.Color.gold()
        )
        
        # Store results in the challenge
        event = self.events[session['event_id']]
        challenge = next(c for c in event.challenges if c.id == session['challenge_id'])
        challenge.results[user.id] = {
            'score': session['score'],
            'total_questions': len(session['questions']),
            'answers': session['answers']
        }
        
        self.save_data()
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
        
        # Clean up session
        del self.trivia_sessions[user.id]

def main():
    """Main function to run the bot"""
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables!")
        return
    
    bot = EventsBot()
    
    try:
        bot.run(bot_token)
    except Exception as e:
        logger.error(f"Failed to run bot: {e}")

if __name__ == "__main__":
    main()