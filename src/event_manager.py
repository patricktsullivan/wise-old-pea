"""
Event Management for Wise Old Pea Bot
Handles event lifecycle, challenge releases, and timing logic
"""

import discord
import datetime
import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from database import Database
from utils import parse_duration, is_event_ended

logger = logging.getLogger('wise_old_pea.event_manager')

class EventManager:
    """
    Manages the complete lifecycle of events from creation to completion
    This class coordinates challenge releases, timing, and event state transitions
    """
    
    def __init__(self, bot, database: Database):
        self.bot = bot
        self.db = database
        self.challenge_data = {}
        self.load_challenges()
    
    def load_challenges(self):
        """Load challenge definitions from JSON file"""
        try:
            logger.info("Loading challenges from challenge_rules.json")
            with open('challenge_rules.json', 'r', encoding='utf-8') as f:
                self.challenge_data = json.load(f)
            logger.info(f"Loaded {len(self.challenge_data.get('challenges', []))} challenges")
        except FileNotFoundError:
            logger.error("challenge_rules.json not found!")
            self.challenge_data = {"challenges": []}
        except Exception as e:
            logger.error(f"Error reading challenge_rules.json: {e}")
            self.challenge_data = {"challenges": []}
    
    async def create_event_interactive(self, admin_user: discord.User, guild: discord.Guild) -> Optional[str]:
        """
        Create a new event through interactive DM setup with admin
        Now much simpler without redundant media collection!
        """
        dm_channel = await admin_user.create_dm()
        
        def check(message):
            return message.author == admin_user and message.channel == dm_channel
        
        try:
            # Step 1: Get event duration (unchanged)
            await dm_channel.send("How long will the event last? (e.g., '7 days', '2 weeks', '1 month')")
            duration_msg = await self.bot.wait_for('message', check=check, timeout=300)
            event_duration = parse_duration(duration_msg.content)
            
            # Step 2: Get release interval (unchanged)
            await dm_channel.send("How often should a new challenge be released? (e.g., '2 hours', '1 day', '3 days')")
            interval_msg = await self.bot.wait_for('message', check=check, timeout=300)
            release_interval = parse_duration(interval_msg.content)
            
            # Step 3: Get event name (unchanged)
            await dm_channel.send("What should this event be called?")
            name_msg = await self.bot.wait_for('message', check=check, timeout=300)
            event_name = name_msg.content.strip()
            
            # Step 4: Get channel for announcements (unchanged)
            await dm_channel.send("Which channel should I post challenges in? (mention it or provide channel ID)")
            channel_msg = await self.bot.wait_for('message', check=check, timeout=300)
            
            channel = await self._parse_channel_from_message(channel_msg, guild)
            if not channel:
                await dm_channel.send("❌ Could not find channel. Event creation cancelled.")
                return None
            
            # Step 5: Create the event (no media collection needed!)
            event_id = await self._create_event_record(
                admin_user, guild, channel, event_name, 
                event_duration, release_interval
            )
            
            # Step 6: Send announcement and release first challenge
            await self._send_event_announcement(channel, event_name, event_duration, release_interval)
            await self.release_next_challenge(event_id)
            
            await dm_channel.send(f"✅ Event '{event_name}' created successfully!")
            return event_id
            
        except Exception as e:
            logger.error(f"Error in event creation: {e}")
            await dm_channel.send(f"❌ An error occurred: {e}")
            return None
    
    async def _parse_channel_from_message(self, message: discord.Message, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Parse channel reference from user message"""
        # Check for channel mentions
        if message.channel_mentions:
            return message.channel_mentions[0]
        
        # Try to parse channel ID
        try:
            channel_id = int(re.search(r'\d+', message.content).group())
            return self.bot.get_channel(channel_id)
        except:
            pass
        
        # Try to find by name
        channel_search = message.content.strip().replace('#', '')
        return discord.utils.get(guild.channels, name=channel_search)
       
    async def _create_event_record(self, admin_user: discord.User, guild: discord.Guild, 
                             channel: discord.TextChannel, event_name: str,
                             event_duration: datetime.timedelta, release_interval: datetime.timedelta) -> str:
        """Create the event database record without media collection"""
        start_time = datetime.datetime.now(datetime.UTC)
        
        event_data = {
            'info': {
                'name': event_name,
                'creator': admin_user.id,
                'guild_id': guild.id,
                'channel_id': channel.id,
                'start_time': start_time,
                'end_time': start_time + event_duration,
                'release_interval': release_interval.total_seconds(),
                'status': 'active',
                'current_challenge_index': 0,
                'last_release': start_time,
                'total_challenges': len(self.challenge_data.get('challenges', []))
            },
            'users': {}
            # Note: No 'media' key needed anymore!
        }
        
        return self.db.create_event(event_data)
    
    async def _send_event_announcement(self, channel: discord.TextChannel, event_name: str,
                                     event_duration: datetime.timedelta, release_interval: datetime.timedelta):
        """Send the initial event announcement to the channel"""
        challenge_names = [challenge['display_name'] for challenge in self.challenge_data.get('challenges', [])]
        
        announcement_embed = discord.Embed(
            title=f"🎉 New Event: {event_name}",
            description="A new event has started! Join now to participate in all challenges.",
            color=0xff6b35
        )
        announcement_embed.add_field(name="📅 Duration", value=str(event_duration), inline=True)
        announcement_embed.add_field(name="⏰ Challenge Release", value=f"Every {release_interval}", inline=True)
        announcement_embed.add_field(name="🎯 Challenges", value="\n".join(challenge_names), inline=False)
        announcement_embed.add_field(name="🚀 How to Join", value=f"Use `!join {event_name}` to participate!", inline=False)
        
        await channel.send(embed=announcement_embed)
    
    async def release_next_challenge(self, event_id: str) -> bool:
        """
        Release the next challenge for an event
        Returns True if a challenge was released, False if no more challenges
        """
        logger.info(f"Releasing next challenge for event {event_id}")
        
        try:
            event_data = self.db.get_event(event_id)
            if not event_data:
                logger.error(f"Event {event_id} not found")
                return False
            
            event_info = event_data['info']
            challenges = self.challenge_data.get('challenges', [])
            
            current_index = event_info['current_challenge_index']
            
            # Check if we've released all challenges
            if current_index >= len(challenges):
                logger.info(f"All challenges released for event {event_id}")
                # Update event to indicate all challenges released
                self.db.update_event(event_id, {
                    'info': {'all_challenges_released': True}
                })
                return False
            
            # Get the challenge to release
            challenge = challenges[current_index]
            channel = self.bot.get_channel(event_info['channel_id'])
            
            if not channel:
                logger.error(f"Could not find channel {event_info['channel_id']} for event {event_id}")
                return False
            
            # Create and send the challenge announcement
            embed = await self._create_challenge_announcement(challenge, event_info['name'])
            
            if 'title_card' in challenge:
                embed.set_image(url=challenge['title_card'])
    
            await channel.send(embed=embed)
            
            # Update event data
            updates = {
                'info': {
                    'current_challenge_index': current_index + 1,
                    'last_release': datetime.datetime.now(datetime.UTC)
                }
            }
            self.db.update_event(event_id, updates)
            
            logger.info(f"Released challenge '{challenge['display_name']}' for event {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing challenge for event {event_id}: {e}")
            return False
    
    async def _create_challenge_announcement(self, challenge: Dict, event_name: str) -> discord.Embed:
        """Create the embed for a challenge announcement using JSON media"""
        embed = discord.Embed(
            title=f"🎯 New Challenge: {challenge['display_name']}",
            description=challenge['rules'],
            color=0xff9900
        )
        embed.add_field(name="Type", value=challenge['type'].title(), inline=True)
        
        if 'duration' in challenge:
            embed.add_field(name="Time Limit", value=f"{challenge['duration']} minutes", inline=True)
        
        # Show exact commands needed
        join_command = f"`!join {challenge['name']}`"
        start_command = f"`!start {challenge['name']}`"
        finish_command = f"`!finish {challenge['name']}`"
        
        embed.add_field(
            name="How to Participate", 
            value=f"1. {join_command} to join\n"
                f"2. {start_command} to begin\n"
                f"3. {finish_command} to complete\n"
                f"4. `!evidence` to submit evidence", 
            inline=False
        )
        
        # Add media directly from challenge definition
        if 'title_card' in challenge:
            embed.set_image(url=challenge['title_card'])
        
        embed.set_footer(text=f"Event: {event_name}")
        return embed
    
    async def check_event_timing(self) -> List[str]:
        """
        Check all active events for timing-related updates
        Returns list of event IDs that had updates
        """
        current_time = datetime.datetime.now(datetime.UTC)
        updated_events = []
        
        try:
            active_event = self.db.get_active_event()
            if not active_event:
                return updated_events
            
            event_data = self.db.get_event(active_event)
            if not event_data:
                return updated_events
            
            event_info = event_data['info']
            
            # Check if event has ended
            if is_event_ended(event_info):
                logger.info(f"Event {active_event} has ended")
                self.db.update_event(active_event, {
                    'info': {'status': 'completed'}
                })
                updated_events.append(active_event)
                return updated_events
            
            # Check if all challenges have been released
            if event_info.get('all_challenges_released', False):
                logger.debug(f"All challenges already released for event {active_event}")
                return updated_events
            
            # Check if it's time for next challenge release
            last_release = event_info.get('last_release')
            if isinstance(last_release, str):
                last_release = datetime.datetime.fromisoformat(last_release.replace('Z', '+00:00'))
            
            interval = datetime.timedelta(seconds=event_info.get('release_interval', 86400))
            
            if current_time - last_release >= interval:
                logger.info(f"Time to release next challenge for event {active_event}")
                if await self.release_next_challenge(active_event):
                    updated_events.append(active_event)
            
        except Exception as e:
            logger.error(f"Error in check_event_timing: {e}")
        
        return updated_events
    
    async def check_challenge_timeouts(self) -> List[tuple[str, str, str]]:
        """
        Check for timed challenges that have expired
        Returns list of (event_id, user_id, challenge_name) tuples for timed out challenges
        """
        current_time = datetime.datetime.now(datetime.UTC)
        timed_out_challenges = []
        
        try:
            active_event = self.db.get_active_event()
            if not active_event:
                return timed_out_challenges
            
            event_data = self.db.get_event(active_event)
            if not event_data or event_data.get('info', {}).get('status') != 'active':
                return timed_out_challenges
            
            for user_id, user_data in event_data.get('users', {}).items():
                for challenge_name, challenge_user_data in user_data.items():
                    if challenge_name in ['joined_at', 'active_challenge']:
                        continue
                    if not isinstance(challenge_user_data, dict):
                        continue
                    if challenge_user_data.get('status') != 'active':
                        continue
                    
                    start_time = challenge_user_data.get('start_time')
                    if not start_time:
                        continue
                    
                    if isinstance(start_time, str):
                        start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    
                    # Find challenge info to get time limit
                    challenge = None
                    for ch in self.challenge_data.get('challenges', []):
                        if ch['name'] == challenge_name:
                            challenge = ch
                            break
                    
                    if not challenge or 'duration' not in challenge:
                        continue
                    
                    time_limit = datetime.timedelta(minutes=int(challenge['duration']))
                    
                    if current_time - start_time >= time_limit:
                        # Mark as timed out
                        updates = {
                            'users': {
                                user_id: {
                                    challenge_name: {
                                        'status': 'finished',
                                        'finish_time': start_time + time_limit,
                                        'duration': time_limit.total_seconds(),
                                        'timed_out': True
                                    }
                                }
                            }
                        }
                        self.db.update_event(active_event, updates)
                        self.db.clear_active_challenge(active_event, user_id)
                        
                        timed_out_challenges.append((active_event, user_id, challenge_name))
                        logger.info(f"Challenge timed out: {user_id} - {challenge_name}")
            
        except Exception as e:
            logger.error(f"Error in check_challenge_timeouts: {e}")
        
        return timed_out_challenges
    
    def is_event_active(self) -> bool:
        """Check if there is currently an active event"""
        active_event = self.db.get_active_event()
        if not active_event:
            return False
        
        event_data = self.db.get_event(active_event)
        if not event_data:
            return False
        
        event_info = event_data['info']
        return event_info.get('status') == 'active' and not is_event_ended(event_info)
    
    def get_challenge_by_name(self, name: str) -> Optional[Dict]:
        """Get challenge data by name"""
        from utils import find_challenge_by_name
        return find_challenge_by_name(self.challenge_data.get('challenges', []), name)