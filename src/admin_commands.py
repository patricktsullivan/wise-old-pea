"""
Admin Commands for Wise Old Pea Bot
Handles all administrative functionality like event creation, user management, scoring
"""

import datetime
import discord
from discord.ext import commands
import logging
from typing import Optional

from database import Database
from event_manager import EventManager
from utils import get_usernames, format_duration, calculate_trivia_score

logger = logging.getLogger('wise_old_pea.admin_commands')

class AdminCommands(commands.Cog):
    """
    All administrative commands organized in a single class
    This provides centralized permission checking and admin-specific functionality
    """
    
    def __init__(self, bot, database: Database, event_manager: EventManager):
        self.bot = bot
        self.db = database
        self.event_manager = event_manager
    
    def _is_admin(self, member: discord.Member) -> bool:
        """
        Check if user has administrative permissions
        This can be expanded to include role-based permissions if needed
        """
        logger.debug(f"Checking admin permissions for {member.display_name} ({member.id})")
        
        # Check for server permissions
        if member.guild_permissions.manage_guild:
            logger.debug(f"{member.display_name} has Manage Guild permission")
            return True
        
        # Role-based checks here if needed
        admin_role = discord.utils.get(member.guild.roles, name="Event Admin")
        if admin_role in member.roles:
            return True
        
        logger.debug(f"{member.display_name} does not have admin permissions")
        return False
    
    async def _check_admin_permissions(self, ctx) -> bool:
        """Check admin permissions and send error message if failed"""
        if not self._is_admin(ctx.author):
            logger.warning(f"Admin command denied - {ctx.author} lacks admin permissions")
            await ctx.send("❌ You don't have permission to use this command.")
            return False
        return True
    
    def _find_user_by_name(self, username: str) -> Optional[tuple[str, dict]]:
        """
        Find user by Discord name or OSRS username
        Returns: (user_id, account_data) tuple or None
        """
        username_lower = username.lower()
        for user_id, account in self.db.accounts.items():
            if (account['discord_name'].lower() == username_lower or 
                account['osrs_username'].lower() == username_lower):
                return user_id, account
        return None
    
    @commands.command(name='create_event')
    async def create_event(self, ctx):
        """
        Admin command to create a new event through interactive DM setup
        Usage: !create_event
        
        This provides a guided experience for setting up complex events
        """
        logger.info(f"Event creation attempt by {ctx.author}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        await ctx.send("📩 Check your DMs to set up the event!")
        
        try:
            event_id = await self.event_manager.create_event_interactive(ctx.author, ctx.guild)
            if event_id:
                logger.info(f"Event {event_id} created successfully by {ctx.author}")
            else:
                logger.warning(f"Event creation failed for {ctx.author}")
        except Exception as e:
            logger.error(f"Error in create_event command: {e}")
            await ctx.send("❌ An error occurred during event creation. Please check the logs.")
    
    @commands.command(name='admin_scores')
    async def admin_scores(self, ctx, *, target_user: str = None):
        """
        Admin command to view all scores or specific user scores
        Usage: !admin_scores [username]
        
        Shows detailed information about user progress and challenge data
        """
        logger.info(f"Admin scores requested by {ctx.author} for user: {target_user}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        if target_user:
            # Show detailed scores for specific user
            await self._show_user_detailed_scores(ctx, target_user, active_event)
        else:
            # Show summary of all participants
            await self._show_all_users_summary(ctx, active_event)
    
    async def _show_user_detailed_scores(self, ctx, target_user: str, active_event: str):
        """Show detailed scores for a specific user"""
        user_result = self._find_user_by_name(target_user)
        if not user_result:
            await ctx.send(f"❌ User '{target_user}' not found.")
            return
        
        user_id, account = user_result
        user_data = self.db.get_user_event_data(active_event, user_id)
        
        if not user_data:
            await ctx.send(f"❌ User '{account['osrs_username']}' hasn't joined the current event.")
            return
        
        embed = discord.Embed(
            title=f"📊 Admin View - {account['osrs_username']}",
            description=f"Discord: {account['discord_name']}",
            color=0xff0000
        )
        
        total_completed = 0
        total_in_progress = 0
        
        for challenge_name, challenge_data in user_data.items():
            if challenge_name in ['joined_at', 'active_challenge']:
                continue
            if not isinstance(challenge_data, dict):
                continue
            
            # Find the display name for this challenge
            challenge_obj = self.event_manager.get_challenge_by_name(challenge_name)
            display_name = challenge_obj['display_name'] if challenge_obj else challenge_name.title()
            
            status = challenge_data.get('status', 'not_started')
            status_parts = []
            
            if status == 'finished':
                total_completed += 1
                duration = challenge_data.get('duration', 0)
                duration_str = format_duration(duration)
                status_parts.append(f"✅ Completed ({duration_str})")
                
                # Add trivia score if applicable
                trivia_score = calculate_trivia_score(challenge_data)
                if trivia_score > 0:
                    total_trivia = len(challenge_data.get('trivia_answers', {}))
                    status_parts.append(f"Trivia: {trivia_score}/{total_trivia}")
                
            elif status == 'active':
                total_in_progress += 1
                status_parts.append("🔄 In Progress")
                
                # Show current stage if available
                stage = challenge_data.get('stage')
                if stage:
                    status_parts.append(f"Stage: {stage}")
            else:
                status_parts.append("⭕ Not Started")
            
            # Add evidence count
            evidence_count = len(challenge_data.get('evidence', []))
            if evidence_count > 0:
                status_parts.append(f"Evidence: {evidence_count}")
            
            # Show if timed out
            if challenge_data.get('timed_out'):
                status_parts.append("⏰ Timed Out")
            
            embed.add_field(
                name=display_name,
                value=" | ".join(status_parts),
                inline=False
            )
        
        # Add summary
        embed.add_field(
            name="📈 Summary",
            value=f"Completed: {total_completed} | In Progress: {total_in_progress}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_all_users_summary(self, ctx, active_event: str):
        """Show summary of all participants"""
        embed = discord.Embed(
            title="📊 Admin Summary - All Participants",
            color=0xff0000
        )
        
        event_data = self.db.get_event(active_event)
        event_users = event_data.get('users', {})
        
        if not event_users:
            embed.add_field(name="No Participants", value="No users have joined this event yet.", inline=False)
            await ctx.send(embed=embed)
            return
        
        participants = []
        
        for user_id, user_data in event_users.items():
            account = self.db.get_account(user_id)
            if not account:
                continue
            
            osrs_name = account['osrs_username']
            completed = 0
            in_progress = 0
            
            for challenge_name, challenge_data in user_data.items():
                if challenge_name in ['joined_at', 'active_challenge']:
                    continue
                if not isinstance(challenge_data, dict):
                    continue
                
                status = challenge_data.get('status', 'not_started')
                if status == 'finished':
                    completed += 1
                elif status == 'active':
                    in_progress += 1
            
            participants.append({
                'name': osrs_name,
                'completed': completed,
                'in_progress': in_progress,
                'total_activity': completed + in_progress
            })
        
        # Sort by total activity (most active first)
        participants.sort(key=lambda x: x['total_activity'], reverse=True)
        
        # Split into chunks if too many participants
        max_fields = 20  # Discord embed field limit
        
        for i, participant in enumerate(participants[:max_fields]):
            embed.add_field(
                name=participant['name'],
                value=f"Completed: {participant['completed']} | In Progress: {participant['in_progress']}",
                inline=True
            )
        
        if len(participants) > max_fields:
            embed.add_field(
                name="...",
                value=f"And {len(participants) - max_fields} more participants",
                inline=False
            )
        
        embed.add_field(
            name="📊 Totals",
            value=f"Total Participants: {len(participants)}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='set_stage')
    async def set_stage(self, ctx, username: str, *, stage: str):
        """
        Admin command to set user's challenge stage
        Usage: !set_stage <username> <stage>
        
        This is useful for fixing issues or manually advancing users
        """
        logger.info(f"Set stage attempt by {ctx.author} for user: {username}, stage: {stage}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Find the user
        user_result = self._find_user_by_name(username)
        if not user_result:
            await ctx.send(f"❌ User '{username}' not found.")
            return
        
        user_id, account = user_result
        
        # Find user's active challenge
        active_challenge_name = self.db.get_active_challenge(active_event, user_id)
        if not active_challenge_name:
            await ctx.send(f"❌ User '{account['osrs_username']}' doesn't have an active challenge.")
            return
        
        # Find the challenge object
        challenge = self.event_manager.get_challenge_by_name(active_challenge_name)
        if not challenge:
            await ctx.send("❌ Could not find challenge data.")
            return
        
        # Check if challenge supports stages (only certain challenges do)
        stage_supported_challenges = ['peas_place', 'final_examine']  # Add more as needed
        if challenge['name'] not in stage_supported_challenges:
            await ctx.send(f"❌ Challenge '{challenge['display_name']}' doesn't support stage setting.")
            return
        
        # Set the stage
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, challenge['name'])
        challenge_data['stage'] = stage
        self.db.save_database()
        
        logger.info(f"Admin {ctx.author} set {account['osrs_username']}'s stage to {stage} for {challenge['display_name']}")
        await ctx.send(f"✅ Set {account['osrs_username']}'s stage to **{stage}** for challenge **{challenge['display_name']}**.")
    
    @commands.command(name='reset')
    async def reset_challenge(self, ctx, username: str, *, challenge_name: str):
        """
        Admin command to reset user's challenge data
        Usage: !reset <username> <challenge_name>
        
        This completely resets a user's progress on a specific challenge
        """
        logger.info(f"Reset attempt by {ctx.author} for user: {username}, challenge: {challenge_name}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Find the user
        user_result = self._find_user_by_name(username)
        if not user_result:
            await ctx.send(f"❌ User '{username}' not found.")
            return
        
        user_id, account = user_result
        
        # Find the challenge
        challenge = self.event_manager.get_challenge_by_name(challenge_name)
        if not challenge:
            await ctx.send(f"❌ Challenge '{challenge_name}' not found.")
            return
        
        # Check if user has this challenge
        user_data = self.db.get_user_event_data(active_event, user_id)
        if challenge['name'] not in user_data:
            await ctx.send(f"❌ User '{account['osrs_username']}' doesn't have challenge '{challenge['display_name']}'.")
            return
        
        # Clear active challenge if this is it
        active_challenge = self.db.get_active_challenge(active_event, user_id)
        if active_challenge and active_challenge == challenge['name']:
            self.db.clear_active_challenge(active_event, user_id)
        
        # Remove challenge data by updating the event
        updates = {
            'users': {
                user_id: {
                    challenge['name']: None  # This will remove the key
                }
            }
        }
        
        # Manually remove the challenge data
        event_data = self.db.get_event(active_event)
        if challenge['name'] in event_data['users'][user_id]:
            del event_data['users'][user_id][challenge['name']]
        self.db.save_database()
        
        logger.info(f"Admin {ctx.author} reset {account['osrs_username']}'s data for {challenge['display_name']}")
        await ctx.send(f"✅ Reset {account['osrs_username']}'s data for challenge **{challenge['display_name']}**. They can now restart it.")
    
    @commands.command(name='event_status')
    async def event_status(self, ctx):
        """
        Admin command to check current event status
        Usage: !event_status
        
        Shows information about the current event, progress, and timing
        """
        logger.info(f"Event status requested by {ctx.author}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        event_data = self.db.get_event(active_event)
        event_info = event_data['info']
        
        embed = discord.Embed(
            title=f"🎯 Event Status: {event_info['name']}",
            color=0x0099ff
        )
        
        # Basic event info
        start_time = event_info['start_time']
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        end_time = event_info['end_time']
        if isinstance(end_time, str):
            end_time = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        embed.add_field(name="Start Time", value=start_time.strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        embed.add_field(name="End Time", value=end_time.strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        embed.add_field(name="Status", value=event_info.get('status', 'unknown').title(), inline=True)
        
        # Challenge progress
        current_index = event_info.get('current_challenge_index', 0)
        total_challenges = event_info.get('total_challenges', len(self.event_manager.challenge_data.get('challenges', [])))
        
        embed.add_field(name="Challenges Released", value=f"{current_index}/{total_challenges}", inline=True)
        
        # Participant count
        participant_count = len(event_data.get('users', {}))
        embed.add_field(name="Participants", value=str(participant_count), inline=True)
        
        # Time until next release
        if not event_info.get('all_challenges_released', False):
            last_release = event_info.get('last_release')
            if isinstance(last_release, str):
                last_release = datetime.datetime.fromisoformat(last_release.replace('Z', '+00:00'))
            
            release_interval = datetime.timedelta(seconds=event_info.get('release_interval', 86400))
            next_release = last_release + release_interval
            time_until_next = next_release - datetime.datetime.now(datetime.UTC)
            
            if time_until_next.total_seconds() > 0:
                embed.add_field(name="Next Release In", value=format_duration(time_until_next.total_seconds()), inline=True)
            else:
                embed.add_field(name="Next Release", value="Due now!", inline=True)
        else:
            embed.add_field(name="Next Release", value="All challenges released", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='force_release')
    async def force_release(self, ctx):
        """
        Admin command to manually release the next challenge
        Usage: !force_release
        
        This bypasses the normal timing and immediately releases the next challenge
        """
        logger.info(f"Force release requested by {ctx.author}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Attempt to release next challenge
        success = await self.event_manager.release_next_challenge(active_event)
        
        if success:
            await ctx.send("✅ Successfully released the next challenge!")
            logger.info(f"Admin {ctx.author} manually released next challenge")
        else:
            await ctx.send("❌ No more challenges to release or an error occurred.")
            logger.warning(f"Force release failed for admin {ctx.author}")

    @commands.command(name='advance_peas_place')
    async def advance_peas_place(self, ctx, username: str):
        """
        Admin command to manually advance a user's Pea's Place stage (for testing)
        Usage: !advance_peas_place <username>
        """
        logger.info(f"Manual Pea's Place advance by {ctx.author} for user: {username}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Find the user
        user_result = self._find_user_by_name(username)
        if not user_result:
            await ctx.send(f"❌ User '{username}' not found.")
            return
        
        user_id, account = user_result
        
        # Check if user has active Pea's Place challenge
        active_challenge = self.db.get_active_challenge(active_event, user_id)
        if active_challenge != 'peas_place':
            await ctx.send(f"❌ User '{account['osrs_username']}' doesn't have Pea's Place as active challenge.")
            return
        
        # Get Discord user
        discord_user = self.bot.get_user(int(user_id))
        if not discord_user:
            await ctx.send("❌ Could not find Discord user.")
            return
        
        # Find the challenge object and advance
        challenge = self.event_manager.get_challenge_by_name('peas_place')
        if challenge:
            from challenge_handlers import ChallengeHandlerFactory
            factory = ChallengeHandlerFactory(self.bot, self.db)
            handler = factory.get_handler(challenge)
            
            advanced = await handler.advance_stage_within_location(discord_user, challenge, active_event, user_id)
            if advanced:
                await ctx.send(f"✅ Advanced {account['osrs_username']}'s Pea's Place stage.")
            else:
                await ctx.send(f"❌ Could not advance {account['osrs_username']}'s stage (probably at max for location).")
        else:
            await ctx.send("❌ Could not find Pea's Place challenge.")

    # Pea's Place Debugging Commands:

    @commands.command(name='peas_place_debug')
    async def peas_place_debug(self, ctx, username: str):
        """
        Admin command to debug Pea's Place state for a user
        Usage: !peas_place_debug <username>
        """
        logger.info(f"Pea's Place debug by {ctx.author} for user: {username}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Find the user
        user_result = self._find_user_by_name(username)
        if not user_result:
            await ctx.send(f"❌ User '{username}' not found.")
            return
        
        user_id, account = user_result
        
        # Get user's challenge data
        challenge_data = self.db.get_user_challenge_data(active_event, user_id, 'peas_place')
        
        embed = discord.Embed(
            title=f"🐛 Pea's Place Debug: {account['osrs_username']}",
            color=0xff0000
        )
        
        status = challenge_data.get('status', 'not_started')
        stage = challenge_data.get('stage', 'none')
        last_stage_time = challenge_data.get('last_stage_time', 'none')
        active_challenge = self.db.get_active_challenge(active_event, user_id)
        
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Current Stage", value=stage, inline=True)
        embed.add_field(name="Active Challenge", value=active_challenge or 'none', inline=True)
        
        if last_stage_time:
            if isinstance(last_stage_time, str):
                last_stage_time = datetime.datetime.fromisoformat(last_stage_time.replace('Z', '+00:00'))
            
            current_time = datetime.datetime.now(datetime.UTC)
            elapsed = (current_time - last_stage_time).total_seconds() / 60
            embed.add_field(name="Last Stage Time", value=f"{last_stage_time.strftime('%H:%M:%S')} UTC", inline=True)
            embed.add_field(name="Minutes Elapsed", value=f"{elapsed:.1f}", inline=True)
        else:
            embed.add_field(name="Last Stage Time", value="Not set", inline=True)
            embed.add_field(name="Minutes Elapsed", value="N/A", inline=True)
        
        evidence_count = len(challenge_data.get('evidence', []))
        embed.add_field(name="Evidence Count", value=str(evidence_count), inline=True)
        
        await ctx.send(embed=embed)

    # CURRENTLY BROKEN
    @commands.command(name='debug_media')
    async def debug_media(self, ctx, location: str, stage: str):
        """
        Debug command to test media lookup
        Usage: !debug_media 1 2  (for location 1, stage 2)
        """
        if not await self._check_admin_permissions(ctx):
            return
        
        media_key = f"{location}.{stage}"
        
        # Load challenge data
        challenge = self.event_manager.get_challenge_by_name('peas_place')
        if not challenge:
            await ctx.send("❌ Could not find peas_place challenge")
            return
        
        await ctx.send(f"🔍 Looking for media key: `{media_key}`")
        
        # Debug the information structure
        information = challenge.get('information', [])
        await ctx.send(f"📋 Information contains {len(information)} objects")
        
        for i, info_item in enumerate(information):
            if isinstance(info_item, dict):
                keys = list(info_item.keys())
                await ctx.send(f"Object {i}: {len(keys)} keys: {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}")
                
                if media_key in info_item:
                    media_url = info_item[media_key]
                    await ctx.send(f"✅ Found media URL: {media_url}")
                    
                    # Test if the URL is accessible
                    embed = discord.Embed(
                        title=f"Media Test: {media_key}",
                        description="Testing media accessibility",
                        color=0x00ff00
                    )
                    embed.set_image(url=media_url)
                    await ctx.send(embed=embed)
                    return
            else:
                await ctx.send(f"Object {i}: Not a dictionary (type: {type(info_item)})")
        
        await ctx.send(f"❌ Media key `{media_key}` not found in any information object")

    # CURRENTLY BROKEN
    @commands.command(name='list_media')
    async def list_media(self, ctx):
        """
        List all available media keys for Pea's Place
        Usage: !list_media
        """
        if not await self._check_admin_permissions(ctx):
            return
        
        challenge = self.event_manager.get_challenge_by_name('peas_place')
        if not challenge:
            await ctx.send("❌ Could not find peas_place challenge")
            return
        
        information = challenge.get('information', [])
        all_keys = []
        
        for i, info_item in enumerate(information):
            if isinstance(info_item, dict):
                keys = list(info_item.keys())
                all_keys.extend(keys)
        
        if all_keys:
            all_keys.sort()
            # Split into chunks for Discord message limit
            chunk_size = 50
            for i in range(0, len(all_keys), chunk_size):
                chunk = all_keys[i:i+chunk_size]
                embed = discord.Embed(
                    title=f"📋 Available Media Keys ({i+1}-{min(i+chunk_size, len(all_keys))} of {len(all_keys)})",
                    description="\n".join(chunk),
                    color=0x0099ff
                )
                await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No media keys found")

    @commands.command(name='test_peas_advance')
    async def test_peas_advance(self, ctx, username: str):
        """
        Admin command to test Pea's Place advancement with full user lookup
        Usage: !test_peas_advance <username>
        """
        logger.info(f"Testing Pea's Place advance by {ctx.author} for user: {username}")
        
        if not await self._check_admin_permissions(ctx):
            return
        
        active_event = self.db.get_active_event()
        if not active_event:
            await ctx.send("❌ No active event found.")
            return
        
        # Find the user in database
        user_result = self._find_user_by_name(username)
        if not user_result:
            await ctx.send(f"❌ User '{username}' not found.")
            return
        
        user_id, account = user_result
        
        # Check if user has active Pea's Place challenge
        active_challenge = self.db.get_active_challenge(active_event, user_id)
        if active_challenge != 'peas_place':
            await ctx.send(f"❌ User '{account['osrs_username']}' doesn't have Pea's Place as active challenge.")
            return
        
        await ctx.send(f"🔍 Testing advancement for {account['osrs_username']}...")
        
        # Try multiple methods to get the Discord user
        discord_user = None
        
        # Method 1: bot.get_user
        discord_user = self.bot.get_user(int(user_id))
        if discord_user:
            await ctx.send(f"✅ Found user via get_user: {discord_user}")
        else:
            await ctx.send(f"❌ get_user failed for ID {user_id}")
            
            # Method 2: bot.fetch_user
            try:
                discord_user = await self.bot.fetch_user(int(user_id))
                await ctx.send(f"✅ Found user via fetch_user: {discord_user}")
            except Exception as e:
                await ctx.send(f"❌ fetch_user failed: {e}")
                
                # Method 3: Look through guild members
                for guild in self.bot.guilds:
                    member = guild.get_member(int(user_id))
                    if member:
                        discord_user = member
                        await ctx.send(f"✅ Found user via guild member: {discord_user}")
                        break
                
                if not discord_user:
                    await ctx.send(f"❌ Could not find Discord user through any method")
                    return
        
        # Now try the advancement
        challenge = self.event_manager.get_challenge_by_name('peas_place')
        if challenge:
            from challenge_handlers import ChallengeHandlerFactory
            factory = ChallengeHandlerFactory(self.bot, self.db)
            handler = factory.get_handler(challenge)
            
            # Get current state
            challenge_data = self.db.get_user_challenge_data(active_event, user_id, 'peas_place')
            current_stage = challenge_data.get('stage', '1.1')
            
            await ctx.send(f"Current stage: {current_stage}")
            
            advanced = await handler.advance_stage_within_location(discord_user, challenge, active_event, user_id)
            if advanced:
                # Get new state
                challenge_data = self.db.get_user_challenge_data(active_event, user_id, 'peas_place')
                new_stage = challenge_data.get('stage', '1.1')
                await ctx.send(f"✅ Advanced from {current_stage} to {new_stage}")
            else:
                await ctx.send(f"❌ Could not advance from {current_stage}")
        else:
            await ctx.send("❌ Could not find Pea's Place challenge.")









            
