"""
User Commands for Wise Old Pea Bot
Handles all regular user commands like join, start, finish, evidence, etc.
"""

import discord
from discord.ext import commands
import datetime
import logging
import re
from typing import Optional

from database import Database
from event_manager import EventManager
from challenge_handlers import ChallengeHandlerFactory
from utils import get_usernames, format_duration, calculate_trivia_score, is_event_ended

logger = logging.getLogger('wise_old_pea.user_commands')

class UserCommands(commands.Cog):
    """
    All user-facing commands organized in a single class
    This makes it easy to manage permissions, error handling, and common functionality
    """
    
    def __init__(self, bot, database: Database, event_manager: EventManager):
        self.bot = bot
        self.db = database
        self.event_manager = event_manager
        self.challenge_factory = ChallengeHandlerFactory(bot, database)
    
    def _check_event_status(self) -> tuple[bool, str, Optional[str]]:
        """
        Check if there's an active event and if commands should be processed
        Returns: (should_process, message_if_not, event_id_if_active)
        This centralizes our event state checking logic
        """
        active_event = self.db.get_active_event()
        
        if not active_event:
            return False, "❌ No active event found.", None
        
        event_data = self.db.get_event(active_event)
        if not event_data:
            return False, "❌ Event data not found.", None
        
        event_info = event_data['info']
        
        # Check if event has ended
        if is_event_ended(event_info):
            return False, "❌ This event has concluded. Use `!my_scores` to see your final results!", None
        
        return True, "", active_event
    
    def _check_user_account(self, user_id: str) -> tuple[bool, str]:
        """
        Check if user has linked their account
        Returns: (has_account, message_if_not)
        """
        if user_id not in self.db.accounts:
            return False, "❌ You must link your OSRS account first using `!link_account <username>`"
        return True, ""
    
    @commands.command(name='link_account')
    async def link_account(self, ctx, *, osrs_username: str = None):
        """
        Link Discord account to OSRS account
        Usage: !link_account <osrs_username>
        
        The * syntax captures everything after the command as one argument,
        solving the space problem the user mentioned
        """
        logger.info(f"Account link attempt by {ctx.author} with username: {osrs_username}")
        
        if not osrs_username:
            await ctx.send("Please provide your OSRS username: `!link_account <username>`")
            return
        
        user_id = str(ctx.author.id)
        self.db.link_account(user_id, ctx.author.display_name, osrs_username)
        
        logger.info(f"Successfully linked {ctx.author} to OSRS account: {osrs_username}")
        await ctx.send(f"✅ Successfully linked Discord account to OSRS account: **{osrs_username}**")
    
    @commands.command(name='join')
    async def join(self, ctx, *, target: str = None):
        """
        Join a specific challenge or event
        Usage: !join <challenge_name> or !join <event_name>
        
        This command uses the 'name' field for matching, not 'display_name'
        """
        logger.info(f"Join attempt by {ctx.author} for target: '{target}'")
        
        if not target:
            await ctx.send("Please specify a challenge or event name: `!join <challenge_name>` or `!join <event_name>`")
            return
        
        user_id = str(ctx.author.id)
        
        # Check if user has linked account
        has_account, account_msg = self._check_user_account(user_id)
        if not has_account:
            await ctx.send(account_msg)
            return
        
        # Check event status
        event_active, event_msg, active_event = self._check_event_status()
        if not event_active:
            await ctx.send(event_msg)
            return
        
        event_data = self.db.get_event(active_event)
        event_info = event_data['info']
        
        # Normalize the target for comparison (using our utility function)
        from utils import normalize_text
        target_normalized = normalize_text(target)
        
        # Check if joining an event by name
        event_name_normalized = normalize_text(event_info['name'])
        if target_normalized == event_name_normalized:
            # Add user to event
            self.db.add_user_to_event(active_event, user_id)
            logger.info(f"{ctx.author} joined event: {event_info['name']}")
            await ctx.send(f"✅ Joined event: **{event_info['name']}**! You can now start challenges.")
            return
        
        # Check if joining a specific challenge by name (not display_name)
        challenge = self.event_manager.get_challenge_by_name(target)
        if challenge:
            # Add user to event if not already there
            if not self.db.is_user_in_event(active_event, user_id):
                self.db.add_user_to_event(active_event, user_id)
            
            # Initialize challenge data (this creates the structure if needed)
            self.db.get_user_challenge_data(active_event, user_id, challenge['name'])
            
            logger.info(f"{ctx.author} joined challenge: {challenge['display_name']}")
            await ctx.send(f"✅ Joined challenge: **{challenge['display_name']}**!")
        else:
            logger.warning(f"Join failed - challenge/event '{target}' not found for {ctx.author}")
            await ctx.send(f"❌ Challenge or event '{target}' not found.")
    
    @commands.command(name='start')
    async def start_challenge(self, ctx, *, challenge_name: str = None):
        """
        Start a challenge timer
        Usage: !start <challenge_name>
        
        This is where we implement the challenge-specific logic using our handlers
        """
        logger.info(f"Start attempt by {ctx.author} for challenge: '{challenge_name}'")
        
        if not challenge_name:
            await ctx.send("Please specify a challenge name: `!start <challenge_name>`")
            return
        
        user_id = str(ctx.author.id)
        
        # Check prerequisites
        has_account, account_msg = self._check_user_account(user_id)
        if not has_account:
            await ctx.send(account_msg)
            return
        
        event_active, event_msg, active_event = self._check_event_status()
        if not event_active:
            await ctx.send(event_msg)
            return
        
        # Check if user has another active challenge
        current_active = self.db.get_active_challenge(active_event, user_id)
        if current_active:
            # Find the display name for the current active challenge
            active_challenge_obj = self.event_manager.get_challenge_by_name(current_active)
            active_display_name = active_challenge_obj['display_name'] if active_challenge_obj else current_active
            
            logger.warning(f"Start failed - {ctx.author} already has active challenge: {active_display_name}")
            await ctx.send(f"❌ You already have an active challenge: **{active_display_name}**. Finish it first or contact an admin.")
            return
        
        # Find the challenge by name (not display_name)
        challenge = self.event_manager.get_challenge_by_name(challenge_name)
        if not challenge:
            logger.warning(f"Start failed - challenge '{challenge_name}' not found for {ctx.author}")
            await ctx.send(f"❌ Challenge '{challenge_name}' not found.")
            return
        
        # Check if user is in the event
        if not self.db.is_user_in_event(active_event, user_id):
            await ctx.send("❌ You must join the event first using `!join`")
            return
        
        # Get challenge data and check status
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, challenge['name'])
        
        if challenge_data['status'] == 'active':
            await ctx.send(f"❌ You've already started '{challenge['display_name']}'. Use `!finish {challenge['name']}` to complete it.")
            return
        
        if challenge_data['status'] == 'finished':
            await ctx.send(f"❌ You've already finished '{challenge['display_name']}'.")
            return
        
        # Start the challenge
        start_time = datetime.datetime.now(datetime.UTC)
        challenge_data.update({
            'status': 'active',
            'start_time': start_time,
            'stage': '1'
        })
        
        self.db.set_active_challenge(active_event, user_id, challenge['name'])
        self.db.save_database()
        
        logger.info(f"{ctx.author} started challenge: {challenge['display_name']}")
        
        # Get appropriate handler and start the challenge
        handler = self.challenge_factory.get_handler(challenge)
        
        # Handle DM challenges differently
        if challenge.get('location') == 'DM':
            dm_message = await handler.handle_start(ctx.author, challenge, active_event)
            username_display = get_usernames(self.db.accounts, user_id, ctx.author.display_name)
            await ctx.send(f"{username_display} 🚀 Started **{challenge['display_name']}**! {dm_message}")
            return
        
        # Handle regular challenges with public announcement
        username_display = get_usernames(self.db.accounts, user_id, ctx.author.display_name)
        embed = discord.Embed(
            title=f"{username_display} 🚀 Started: {challenge['display_name']}",
            description=challenge['rules'],
            color=0x00ff00
        )
        embed.add_field(name="Type", value=challenge['type'].title(), inline=True)
        
        if 'duration' in challenge:
            embed.add_field(name="Time Limit", value=f"{challenge['duration']} minutes", inline=True)
        
        embed.set_footer(text=f"Started at {start_time.strftime('%H:%M:%S UTC')}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='finish')
    async def finish_challenge(self, ctx, *, challenge_name: str = None):
        """
        Finish a challenge
        Usage: !finish <challenge_name>
        
        This fixes the issue where challenge names were getting concatenated
        """
        logger.info(f"Finish attempt by {ctx.author} for challenge: '{challenge_name}'")
        
        if not challenge_name:
            await ctx.send("Please specify a challenge name: `!finish <challenge_name>`")
            return
        
        user_id = str(ctx.author.id)
        
        # Check event status
        event_active, event_msg, active_event = self._check_event_status()
        if not event_active:
            await ctx.send(event_msg)
            return
        
        # Find the challenge by name (not display_name)
        challenge = self.event_manager.get_challenge_by_name(challenge_name)
        if not challenge:
            logger.warning(f"Finish failed - challenge '{challenge_name}' not found for {ctx.author}")
            await ctx.send(f"❌ Challenge '{challenge_name}' not found.")
            return
        
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, challenge['name'])
        
        if challenge_data['status'] != 'active':
            await ctx.send(f"❌ You haven't started '{challenge['display_name']}' or have already finished it.")
            return
        
        # Record finish time and calculate duration
        finish_time = datetime.datetime.now(datetime.UTC)
        start_time = challenge_data.get('start_time')
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        duration = finish_time - start_time
        
        challenge_data.update({
            'status': 'finished',
            'finish_time': finish_time,
            'duration': duration.total_seconds()
        })
        
        self.db.clear_active_challenge(active_event, user_id)
        self.db.save_database()
        
        logger.info(f"{ctx.author} finished challenge: {challenge['display_name']} in {duration}")
        
        embed = discord.Embed(
            title=f"✅ Completed: {challenge['display_name']}",
            description=f"Time taken: {format_duration(duration.total_seconds())}",
            color=0x00ff00
        )
        embed.set_footer(text=f"Finished at {finish_time.strftime('%H:%M:%S UTC')} | Use !evidence to submit evidence")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='evidence')
    async def submit_evidence(self, ctx, *, challenge_name: str = None):
        """
        Submit evidence for a challenge
        Usage: !evidence [challenge_name]
        
        This implements the smart defaulting behavior the user requested:
        1. If challenge_name provided, use that
        2. If no name provided, default to active challenge
        3. If no active challenge, default to most recently finished
        4. If none of the above, give helpful error message
        """
        logger.info(f"Evidence submission by {ctx.author} for challenge: '{challenge_name}'")
        
        user_id = str(ctx.author.id)
        
        # Check event status
        event_active, event_msg, active_event = self._check_event_status()
        if not event_active:
            await ctx.send(event_msg)
            return
        
        # Smart challenge detection logic
        target_challenge = None
        target_challenge_name = None
        
        if challenge_name:
            # Specific challenge requested
            target_challenge = self.event_manager.get_challenge_by_name(challenge_name)
            if not target_challenge:
                await ctx.send(f"❌ Challenge '{challenge_name}' not found.")
                return
            target_challenge_name = target_challenge['name']
        else:
            # Auto-detect: first try active challenge
            active_challenge_name = self.db.get_active_challenge(active_event, user_id)
            if active_challenge_name:
                target_challenge = self.event_manager.get_challenge_by_name(active_challenge_name)
                target_challenge_name = active_challenge_name
            else:
                # No active challenge, find most recently finished
                user_data = self.db.get_user_event_data(active_event, user_id)
                most_recent_time = None
                
                for challenge_name_key, data in user_data.items():
                    if challenge_name_key in ['joined_at', 'active_challenge']:
                        continue
                    if isinstance(data, dict) and data.get('status') == 'finished':
                        finish_time = data.get('finish_time')
                        if isinstance(finish_time, str):
                            finish_time = datetime.datetime.fromisoformat(finish_time.replace('Z', '+00:00'))
                        if most_recent_time is None or finish_time > most_recent_time:
                            most_recent_time = finish_time
                            target_challenge_name = challenge_name_key
                            target_challenge = self.event_manager.get_challenge_by_name(challenge_name_key)
                
                if not target_challenge_name:
                    await ctx.send("❌ No challenges to submit evidence for. You need to `!join`, `!start`, or `!finish` a challenge first.")
                    return
        
        # Get challenge data
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, target_challenge_name)
        
        # Collect evidence from the message
        evidence_list = []
        
        # Check for attachments (screenshots, files)
        if ctx.message.attachments:
            logger.info(f"Found {len(ctx.message.attachments)} attachments from {ctx.author}")
            for attachment in ctx.message.attachments:
                evidence_list.append({
                    'type': 'attachment',
                    'url': attachment.url,
                    'filename': attachment.filename,
                    'submitted_at': datetime.datetime.now(datetime.UTC)
                })
        
        # Check for URLs in message content
        url_pattern = r'https?://\S+'
        urls = re.findall(url_pattern, ctx.message.content)
        if urls:
            logger.info(f"Found {len(urls)} URLs from {ctx.author}")
            for url in urls:
                evidence_list.append({
                    'type': 'url',
                    'url': url,
                    'submitted_at': datetime.datetime.now(datetime.UTC)
                })
        
        if not evidence_list:
            await ctx.send("❌ No evidence found. Please attach screenshots or provide URLs.")
            return
        
        # Store the evidence
        challenge_data['evidence'].extend(evidence_list)
        self.db.save_database()
        
        display_name = target_challenge['display_name'] if target_challenge else target_challenge_name
        logger.info(f"{ctx.author} submitted {len(evidence_list)} evidence items for {display_name}")
        
        embed = discord.Embed(
            title=f"📸 Evidence Submitted: {display_name}",
            description=f"Collected {len(evidence_list)} evidence items",
            color=0x0099ff
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='my_scores')
    async def my_scores(self, ctx):
        """
        Display user's personal scores
        Usage: !my_scores
        
        This shows scores even after events end, as requested
        """
        logger.info(f"Scores requested by {ctx.author}")
        
        user_id = str(ctx.author.id)
        
        # Check if user has linked account
        has_account, account_msg = self._check_user_account(user_id)
        if not has_account:
            await ctx.send(account_msg)
            return
        
        # Get active event (or most recent if no active event)
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No recent event found.")
            return
        
        user_data = self.db.get_user_event_data(active_event, user_id)
        
        if not user_data:
            await ctx.send("You haven't joined any recent events yet!")
            return
        
        osrs_username = self.db.accounts[user_id]['osrs_username']
        embed = discord.Embed(
            title=f"📊 Scores for {osrs_username}",
            color=0x0099ff
        )
        
        challenge_count = 0
        for challenge_name, challenge_data in user_data.items():
            if challenge_name in ['joined_at', 'active_challenge']:
                continue
            if not isinstance(challenge_data, dict):
                continue
            
            challenge_count += 1
            
            # Find the display name for this challenge
            challenge_obj = self.event_manager.get_challenge_by_name(challenge_name)
            display_name = challenge_obj['display_name'] if challenge_obj else challenge_name.title()
            
            status = challenge_data.get('status', 'not_started')
            
            if status == 'finished':
                duration = challenge_data.get('duration', 0)
                duration_str = format_duration(duration)
                
                # Add trivia score if applicable
                trivia_score = calculate_trivia_score(challenge_data)
                trivia_text = f" | Correct: {trivia_score}" if trivia_score > 0 else ""
                
                status_text = f"✅ Completed ({duration_str}){trivia_text}"
            elif status == 'active':
                status_text = "🔄 In Progress"
            else:
                status_text = "⭕ Not Started"
            
            evidence_count = len(challenge_data.get('evidence', []))
            if evidence_count > 0:
                status_text += f" | Evidence: {evidence_count}"
            
            embed.add_field(
                name=display_name,
                value=status_text,
                inline=False
            )
        
        if challenge_count == 0:
            embed.add_field(name="No Challenges", value="You haven't started any challenges yet!", inline=False)
        
        logger.info(f"Displayed {challenge_count} challenge statuses for {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name='skip')
    async def skip_stage(self, ctx):
        """
        Skip to next stage in DM challenges
        Usage: !skip (only works in DMs)
        
        This command only works in DMs for challenges that support skipping
        """
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("❌ This command only works in DMs during challenges.")
            return
        
        user_id = str(ctx.author.id)
        
        # Check event status
        event_active, event_msg, active_event = self._check_event_status()
        if not event_active:
            await ctx.send(event_msg)
            return
        
        active_challenge_name = self.db.get_active_challenge(active_event, user_id)
        if not active_challenge_name:
            await ctx.send("❌ You're not currently in an active challenge.")
            return
        
        # Find the challenge object
        challenge = self.event_manager.get_challenge_by_name(active_challenge_name)
        if not challenge or challenge.get('skip') != 'yes':
            await ctx.send("❌ This challenge doesn't support skipping.")
            return
        
        # Handle skipping based on challenge type
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, challenge['name'])
        
        # Special case for Pea's Place
        if challenge['name'] ==  'peas_place':
            # Skip stage for location
            logger.debug(f"{ctx.author} skipped stage in the Pea's Place function")
            information = challenge.get('information', {})
            current_stage = challenge_data.get('stage', '1')
            next_stage = str(float(current_stage) + 0.1)
            logger.debug(f"next_stage: {next_stage}")
            logger.debug(f"information: {information}")
            logger.debug(f"next_stage in location for location in information: {any(next_stage in location for location in information)}")

            if any(next_stage in location for location in information):
                challenge_data['stage'] = next_stage
                self.db.save_database()
                
                # Get handler and send next info
                handler = self.challenge_factory.get_handler(challenge)
                # await handler.send_speed_run_info(ctx.author, challenge, next_stage)
                await handler.send_peas_place_media(self, ctx.author, challenge, next_stage, active_event)
                await ctx.send("⏭️ Skipped to next stage.")
            else:
                await ctx.send("🏁 You're already at the final stage!")


        else:
            if challenge['type'] == 'speed_run' and 'information' in challenge:
                logger.debug(f"{ctx.author} skipped stage in {challenge['display_name']}")
                information = challenge.get('information', {})
                current_stage = challenge_data.get('stage', '1')
                next_stage = str(int(current_stage) + 1)
                
                if next_stage in information:
                    challenge_data['stage'] = next_stage
                    self.db.save_database()
                    
                    # Get handler and send next info
                    handler = self.challenge_factory.get_handler(challenge)
                    await handler.send_speed_run_info(ctx.author, challenge, next_stage)
                    await ctx.send("⏭️ Skipped to next stage.")
                else:
                    await ctx.send("🏁 You're already at the final stage!")
        
        logger.info(f"{ctx.author} used skip in challenge {challenge['display_name']}")

