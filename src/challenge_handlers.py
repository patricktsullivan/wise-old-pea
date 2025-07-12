"""
Challenge handlers for different types of challenges in Wise Old Pea Bot
Each challenge type has its own handler class with specific behavior
"""

import discord
import datetime
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod

from utils import validate_answer, format_correct_answer, parse_list_input
from database import Database

logger = logging.getLogger('wise_old_pea.challenge_handlers')

class BaseChallengeHandler(ABC):
    """
    Base class for all challenge handlers
    This defines the common interface that all challenge types must implement
    """
    
    def __init__(self, bot, database: Database):
        self.bot = bot
        self.db = database
    
    @abstractmethod
    async def handle_start(self, user: discord.User, challenge: Dict, event_id: str) -> str:
        """Handle starting a challenge - returns message to send to channel"""
        pass
    
    @abstractmethod
    async def handle_dm_message(self, message: discord.Message, challenge: Dict, event_id: str, user_id: str) -> bool:
        """Handle DM message during challenge - returns True if handled"""
        pass
    
    async def send_dm_safely(self, user: discord.User, content: str = None, embed: discord.Embed = None):
        """Safely send DM to user with error handling"""
        try:
            if embed:
                await user.send(embed=embed)
            else:
                await user.send(content)
            logger.info(f"Sent DM to {user}")
        except discord.Forbidden:
            logger.error(f"Cannot send DM to {user}")
        except Exception as e:
            logger.error(f"Error sending DM to {user}: {e}")

class TriviaHandler(BaseChallengeHandler):
    """
    Handler for trivia challenges with questions and answer validation
    Each user message is validated against the current question
    """
    
    async def handle_start(self, user: discord.User, challenge: Dict, event_id: str) -> str:
        """Start trivia challenge by sending first question"""
        challenge_data = self.db.get_user_challenge_data(event_id, str(user.id), challenge['name'])
        
        # Set initial stage and send first question
        challenge_data['stage'] = '1'
        self.db.save_database()
        
        await self.send_trivia_question(user, challenge, '1')
        return "Check your DMs for the first question."
    
    async def handle_dm_message(self, message: discord.Message, challenge: Dict, event_id: str, user_id: str) -> bool:
        """Handle trivia answer submission"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        
        if challenge_data.get('status') != 'active':
            return False
        
        stage = challenge_data.get('stage', '1')
        
        # Record the answer with timestamp
        if 'trivia_answers' not in challenge_data:
            challenge_data['trivia_answers'] = {}
        
        challenge_data['trivia_answers'][stage] = {
            'user_answer': message.content,
            'timestamp': datetime.datetime.now(datetime.UTC)
        }
        
        # Validate answer
        questions = challenge.get('information', [])
        current_question = self.find_question_by_number(questions, stage)
        
        if current_question:
            correct_answer = current_question.get('a', '')
            answer_type = current_question.get('type', 'exact_match')
            
            # Validate using our utility function
            correct, feedback = validate_answer(message.content, correct_answer, answer_type, current_question)
            
            # Record if correct
            challenge_data['trivia_answers'][stage]['correct'] = correct
            self.db.save_database()
            
            # Send response to user
            response = f"{'✅ Correct!' if correct else '❌ Incorrect.'}"
            if feedback:
                response += f"\n{feedback}"
            
            response += f"\n\n**Answer:** {format_correct_answer(correct_answer, answer_type)}"
            
            # Add explanation if available
            proof = current_question.get('p', '')
            if proof:
                if isinstance(proof, list):
                    response += f"\n\n**Explanation:** {' '.join(proof)}"
                else:
                    response += f"\n\n**Explanation:** {proof}"
            
            await self.send_dm_safely(message.author, response)
            
            # Move to next question or finish
            next_stage = str(int(stage) + 1)
            next_question = self.find_question_by_number(questions, next_stage)
            
            if next_question:
                challenge_data['stage'] = next_stage
                self.db.save_database()
                await self.send_trivia_question(message.author, challenge, next_stage)
            else:
                # Trivia complete
                await self.finish_challenge(message.author, challenge, event_id, user_id)
        
        return True
    
    def find_question_by_number(self, questions: List[Dict], number: str) -> Optional[Dict]:
        """Find question by its number field"""
        for question in questions:
            if question.get('number') == number:
                return question
        return None
    
    async def send_trivia_question(self, user: discord.User, challenge: Dict, stage: str):
        """Send a specific trivia question to user"""
        questions = challenge.get('information', [])
        question_data = self.find_question_by_number(questions, stage)
        
        if question_data:
            question_text = question_data.get('q', '')
            options = question_data.get('o', [])
            
            embed = discord.Embed(
                title=f"Question {stage}",
                description=question_text,
                color=0x0099ff
            )
            
            if options:
                options_text = "\n".join([f"{chr(65+i)}. {option}" for i, option in enumerate(options)])
                embed.add_field(name="Options", value=options_text, inline=False)
            
            await self.send_dm_safely(user, embed=embed)
    
    async def finish_challenge(self, user: discord.User, challenge: Dict, event_id: str, user_id: str):
        """Complete the trivia challenge"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        challenge_data['status'] = 'finished'
        challenge_data['finish_time'] = datetime.datetime.now(datetime.UTC)
        
        # Calculate duration
        start_time = challenge_data.get('start_time')
        if start_time:
            if isinstance(start_time, str):
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            duration = datetime.datetime.now(datetime.UTC) - start_time
            challenge_data['duration'] = duration.total_seconds()
        
        self.db.clear_active_challenge(event_id, user_id)
        self.db.save_database()
        
        await self.send_dm_safely(user, "🎉 Trivia complete!")

class SpeedRunHandler(BaseChallengeHandler):
    """
    Handler for speed run challenges with sequential information
    Used for challenges like Final Examine where any response advances to next stage
    """
    
    async def handle_start(self, user: discord.User, challenge: Dict, event_id: str) -> str:
        """Start speed run challenge by sending first information"""
        challenge_data = self.db.get_user_challenge_data(event_id, str(user.id), challenge['name'])
        
        # Set initial stage and send first info
        challenge_data['stage'] = '1'
        self.db.save_database()
        
        await self.send_speed_run_info(user, challenge, '1')
        return "Check your DMs for the first clue."
    
    async def handle_dm_message(self, message: discord.Message, challenge: Dict, event_id: str, user_id: str) -> bool:
        """Handle any DM message as evidence and advance to next stage"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        
        if challenge_data.get('status') != 'active':
            return False
        
        # Every message counts as evidence submission
        evidence_item = {
            'type': 'text_response',
            'content': message.content,
            'submitted_at': datetime.datetime.now(datetime.UTC)
        }
        
        # Add attachments if any
        if message.attachments:
            for attachment in message.attachments:
                evidence_item = {
                    'type': 'attachment',
                    'url': attachment.url,
                    'filename': attachment.filename,
                    'submitted_at': datetime.datetime.now(datetime.UTC)
                }
                challenge_data['evidence'].append(evidence_item)
        
        # Add URLs if any
        url_pattern = r'https?://\S+'
        urls = re.findall(url_pattern, message.content)
        for url in urls:
            evidence_item = {
                'type': 'url',
                'url': url,
                'submitted_at': datetime.datetime.now(datetime.UTC)
            }
            challenge_data['evidence'].append(evidence_item)
        
        # If just text, store that too
        if message.content.strip():
            evidence_item = {
                'type': 'text_response',
                'content': message.content,
                'submitted_at': datetime.datetime.now(datetime.UTC)
            }
            challenge_data['evidence'].append(evidence_item)
        
        # Move to next stage automatically
        current_stage = challenge_data.get('stage', '1')
        next_stage = str(int(current_stage) + 1)
        
        information = challenge.get('information', {})
        if str(next_stage) in information:
            challenge_data['stage'] = next_stage
            self.db.save_database()
            await self.send_speed_run_info(message.author, challenge, next_stage)
        else:
            # Challenge complete
            await self.finish_challenge(message.author, challenge, event_id, user_id)
        
        return True
    
    async def send_speed_run_info(self, user: discord.User, challenge: Dict, stage: str):
        """Send speed run information directly from challenge definition"""
        information = challenge.get('information', {})
        info_text = information.get(stage, '')
        
        if info_text:
            embed = discord.Embed(
                title=f"{challenge['display_name']} - Stage {stage}",
                description=info_text,
                color=0xff9900
            )
            
            # Add challenge title card if available
            if 'title_card' in challenge:
                embed.set_thumbnail(url=challenge['title_card'])  # Use thumbnail for secondary media
            
            # Add skip note if challenge supports it
            if challenge.get('skip') == 'yes':
                embed.set_footer(text="Type !skip to move to the next stage")
            
            await self.send_dm_safely(user, embed=embed)
        else:
            logger.warning(f"No information found for {challenge['display_name']} stage {stage}")
    
    async def finish_challenge(self, user: discord.User, challenge: Dict, event_id: str, user_id: str):
        """Complete the speed run challenge"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        challenge_data['status'] = 'finished'
        challenge_data['finish_time'] = datetime.datetime.now(datetime.UTC)
        
        # Calculate duration
        start_time = challenge_data.get('start_time')
        if start_time:
            if isinstance(start_time, str):
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            duration = datetime.datetime.now(datetime.UTC) - start_time
            challenge_data['duration'] = duration.total_seconds()
        
        self.db.clear_active_challenge(event_id, user_id)
        self.db.save_database()
        
        await self.send_dm_safely(user, "🎉 All stages completed! Use `!finish` command in the server to complete the challenge.")

class RaceHandler(BaseChallengeHandler):
    """
    Handler for race challenges with initial information dump
    Used for challenges like Spawn Camping where user gets all info at start
    """
    
    async def handle_start(self, user: discord.User, challenge: Dict, event_id: str) -> str:
        """Start race challenge by sending all information"""
        await self.send_race_info(user, challenge)
        return "Check your DMs for the challenge information."
    
    async def handle_dm_message(self, message: discord.Message, challenge: Dict, event_id: str, user_id: str) -> bool:
        """Handle evidence submission for race challenges"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        
        if challenge_data.get('status') != 'active':
            return False
        
        # Collect evidence from message
        evidence_list = []
        
        # Check for attachments
        if message.attachments:
            for attachment in message.attachments:
                evidence_list.append({
                    'type': 'attachment',
                    'url': attachment.url,
                    'filename': attachment.filename,
                    'submitted_at': datetime.datetime.now(datetime.UTC)
                })
        
        # Check for URLs
        url_pattern = r'https?://\S+'
        urls = re.findall(url_pattern, message.content)
        for url in urls:
            evidence_list.append({
                'type': 'url',
                'url': url,
                'submitted_at': datetime.datetime.now(datetime.UTC)
            })
        
        # Store text content
        if message.content.strip():
            evidence_list.append({
                'type': 'text_response',
                'content': message.content,
                'submitted_at': datetime.datetime.now(datetime.UTC)
            })
        
        # Store evidence
        challenge_data['evidence'].extend(evidence_list)
        self.db.save_database()
        
        await self.send_dm_safely(message.author, f"✅ Evidence submitted! ({len(evidence_list)} items collected)")
        
        return True
    
    async def send_race_info(self, user: discord.User, challenge: Dict):
        """Send race information using challenge definition directly"""
        information = challenge.get('information', [])
        
        embed = discord.Embed(
            title=f"{challenge['display_name']}",
            description=challenge['rules'],
            color=0xff9900
        )
        
        # Add title card if available directly from challenge
        if 'title_card' in challenge:
            embed.set_image(url=challenge['title_card'])
        
        # Handle different information formats
        if challenge['name'] == 'spawn_camping':
            # Special formatting for Spawn Camping with numbered anagram list
            if information:
                anagram_list = "\n".join([f"{i+1}. {anagram}" for i, anagram in enumerate(information)])
                embed.add_field(name="List of anagrams:", value=anagram_list, inline=False)
        else:
            # Generic race info handling
            if information:
                if isinstance(information, list):
                    info_text = "\n".join(str(item) for item in information)
                else:
                    info_text = str(information)
                embed.add_field(name="Information", value=info_text, inline=False)
        
        await self.send_dm_safely(user, embed=embed)

class PeasPlaceHandler(BaseChallengeHandler):
    """
    Special handler for Pea's Place challenge with reliable media delivery
    and strict attachment-only evidence validation
    """
    
    async def handle_start(self, user: discord.User, challenge: Dict, event_id: str) -> str:
        """Start Pea's Place by sending first location media"""
        challenge_data = self.db.get_user_challenge_data(event_id, str(user.id), challenge['name'])
        
        # Set initial stage (location.clue format)
        challenge_data['stage'] = '1.1'
        challenge_data['last_stage_time'] = datetime.datetime.now(datetime.UTC)
        
        # IMPORTANT: Save immediately after setting timing data
        self.db.save_database()
        
        logger.info(f"Starting Pea's Place for user {discord.user}, {user.id}: stage=1.1, last_stage_time={challenge_data['last_stage_time']}")
        
        # Send the first location clue
        success = await self.send_peas_place_media(user, challenge, '1', '1', event_id)
        if success:
            return "Check your DMs for the first location clue. More clues will appear over time if needed!"
        else:
            return "Challenge started, but there was an issue loading the first clue. Please contact an admin."
    
    async def handle_dm_message(self, message: discord.Message, challenge: Dict, event_id: str, user_id: str) -> bool:
        """Handle evidence submission - this advances to the NEXT LOCATION"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        
        if challenge_data.get('status') != 'active':
            return False
        
        current_stage = challenge_data.get('stage', '1.1')
        logger.info(f"Processing evidence submission from user {user_id} at stage {current_stage}")
        
        # STRICT VALIDATION: Only accept Discord attachments as evidence
        if not message.attachments:
            if message.content.strip().startswith('!'):
                return False  # Let command system handle it
            
            await self.send_dm_safely(
                message.author, 
                "📸 **Pea's Place requires screenshot evidence!**\n\n"
                "Please attach a screenshot showing you've found the location. "
                "Text descriptions or links won't be accepted for this challenge.\n\n"
                "💡 *Tip: Take a screenshot and drag it into this chat window.*"
            )
            return True
        
        # Collect attachment evidence
        evidence_list = []
        for attachment in message.attachments:
            evidence_list.append({
                'type': 'attachment',
                'url': attachment.url,
                'filename': attachment.filename,
                'location': current_stage,
                'submitted_at': datetime.datetime.now(datetime.UTC)
            })
        
        # Store evidence
        challenge_data['evidence'].extend(evidence_list)
        logger.info(f"Evidence submitted for {user_id} at stage {current_stage}: {len(evidence_list)} items")
        
        # Advance to NEXT LOCATION (not next stage within location)
        await self._advance_to_next_location(message.author, challenge, challenge_data, current_stage, event_id, user_id)
        
        return True
    
    async def _advance_to_next_location(self, user: discord.User, challenge: Dict, challenge_data: Dict, current_stage: str, event_id: str, user_id: str):
        """Advance to the next location (when evidence is submitted)"""
        try:
            category, sub_stage = current_stage.split('.')
            current_location = int(category)
            next_location = current_location + 1
            next_stage = f"{next_location}.1"  # Always start at stage 1 of next location
            
            logger.info(f"Advancing {user_id} from location {current_location} to {next_location}")
            
            # Check if the next location exists
            if self._location_exists(challenge, next_location):
                # Update to next location
                challenge_data['stage'] = next_stage
                challenge_data['last_evidence_time'] = datetime.datetime.now(datetime.UTC)
                challenge_data['last_stage_time'] = datetime.datetime.now(datetime.UTC)  # Reset stage timer
                self.db.save_database()
                
                await self.send_dm_safely(
                    user, 
                    f"✅ **Location {current_location} found!**\n"
                    f"🗺️ Moving to location {next_location}..."
                )
                
                # Send first clue for next location
                success = await self.send_peas_place_media(user, challenge, str(next_location), '1', event_id)
                if not success:
                    logger.error(f"Failed to send media for location {next_location}.1 to user {user_id}")
                
            else:
                # No more locations - challenge complete
                logger.info(f"User {user_id} completed all Pea's Place locations")
                await self.finish_challenge(user, challenge, event_id, user_id)
                
        except Exception as e:
            logger.error(f"Error advancing user {user_id} to next location: {e}")
            await self.send_dm_safely(user, "❌ Error processing your submission. Please contact an admin.")
       
    async def advance_stage_within_location(self, user: discord.User, challenge: Dict, event_id: str, user_id: str) -> bool:
        """
        Advance to next stage within the same location (called by background task)
        Returns True if a new stage was sent, False if no more stages available
        """
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        
        if challenge_data.get('status') != 'active':
            logger.debug(f"Cannot advance stage for user {user_id}: challenge not active (status: {challenge_data.get('status')})")
            return False
        
        current_stage = challenge_data.get('stage', '1.1')
        logger.info(f"Attempting to advance stage for user {user_id} from {current_stage}")
        
        try:
            location_index, stage_index = self._parse_stage(current_stage)
            next_stage_index = stage_index + 1
            
            # Check if there's a next stage within this location
            information = challenge.get('information', [])
            if (location_index < len(information) and 
                isinstance(information[location_index], list) and 
                next_stage_index < len(information[location_index])):
                
                # Update to next stage within same location
                next_stage = f"{location_index + 1}.{next_stage_index + 1}"  # Convert back to 1-based
                challenge_data['stage'] = next_stage
                challenge_data['last_stage_time'] = datetime.datetime.now(datetime.UTC)
                self.db.save_database()
                
                logger.info(f"Advanced {user_id} from {current_stage} to {next_stage}")
                
                # Send the next clue
                success = await self.send_peas_place_media(user, challenge, str(location_index + 1), str(next_stage_index + 1), event_id)
                if success:
                    await self.send_dm_safely(
                        user,
                        f"🔍 **Here's a better view of location {location_index + 1}** (Clue {next_stage_index + 1}/{len(information[location_index])})"
                    )
                    return True
                else:
                    logger.error(f"Failed to send media for stage {next_stage}")
                    return False
            else:
                logger.info(f"No more stages available for location {location_index + 1} after stage {stage_index + 1}")
                return False
                
        except Exception as e:
            logger.error(f"Error advancing stage for user {user_id}: {e}")
            return False
    
    def _stage_exists(self, challenge: Dict, category: str, stage: str) -> bool:
        """Check if a specific stage exists for a location"""
        media_key = f"{category}.{stage}"
        exists = self._find_media_url(challenge, media_key) is not None
        logger.debug(f"Stage exists check: {media_key} = {exists}")
        return exists
    
    def _location_exists(self, challenge: Dict, location_number: int) -> bool:
        """Check if a specific location exists"""
        information = challenge.get('information', [])
        location_index = location_number - 1  # Convert to 0-based
        
        exists = (0 <= location_index < len(information) and 
                isinstance(information[location_index], list) and 
                len(information[location_index]) > 0)
        
        logger.debug(f"Location exists check: location {location_number} (index {location_index}) = {exists}")
        return exists
    
    def _parse_stage(self, stage_str: str) -> tuple[int, int]:
        """
        Parse stage string like '1.1' into location and stage indices
        Returns: (location_index, stage_index) both 0-based
        """
        try:
            location, stage = stage_str.split('.')
            location_index = int(location) - 1  # Convert to 0-based index
            stage_index = int(stage) - 1        # Convert to 0-based index
            return location_index, stage_index
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid stage format '{stage_str}': {e}")
            return 0, 0
    
    async def send_peas_place_media(self, user: discord.User, challenge: Dict, category: str, stage: str, event_id: str) -> bool:
        """
        Send Pea's Place media with enhanced error handling and logging
        Returns True if media was successfully sent, False otherwise
        """
        media_key = f"{category}.{stage}"
        logger.info(f"Sending media for key: {media_key} to user {user.id}")
        
        # Enhanced media lookup with detailed logging
        media_url = self._find_media_url(challenge, media_key)
        
        if media_url:
            try:
                embed = discord.Embed(
                    title=f"🗺️ Pea's Place - Location {category}",
                    description=f"📍 Clue {stage}/5\n\n*Find this location and submit a screenshot as evidence.*",
                    color=0x9932cc
                )
                embed.set_image(url=media_url)
                embed.set_footer(text="💡 Tip: More clues will appear over time if you're stuck!")
                
                await self.send_dm_safely(user, embed=embed)
                logger.info(f"Successfully sent media {media_key} to user {user.id}")
                return True
                
            except Exception as e:
                logger.error(f"Error sending embed for {media_key} to user {user.id}: {e}")
                # Fallback to text message if embed fails
                await self.send_dm_safely(
                    user, 
                    f"📍 Location {category}, Clue {stage}/5\n"
                    f"Image: {media_url}\n"
                    "(There was an issue displaying the image in an embed)"
                )
                return True
        else:
            logger.warning(f"No media found for key {media_key} in challenge {challenge.get('name', 'unknown')}")
            await self.send_dm_safely(
                user, 
                f"📍 **Location {category}, Clue {stage}/5**\n"
                "⚠️ Image not available - please contact an admin."
            )
            return False
    
    def _find_media_url(self, challenge: Dict, media_key: str) -> Optional[str]:
        """
        Enhanced media URL lookup using list-of-lists structure
        media_key format: "1.1" = location 1, stage 1
        """
        information = challenge.get('information', [])
        logger.debug(f"Searching for media key '{media_key}' in {len(information)} location lists")
        
        try:
            location_index, stage_index = self._parse_stage(media_key)
            
            # Validate indices are within bounds
            if location_index < 0 or location_index >= len(information):
                logger.warning(f"Location index {location_index} out of bounds for {len(information)} locations")
                return None
            
            location_list = information[location_index]
            if not isinstance(location_list, list):
                logger.warning(f"Location {location_index} is not a list: {type(location_list)}")
                return None
            
            if stage_index < 0 or stage_index >= len(location_list):
                logger.warning(f"Stage index {stage_index} out of bounds for location {location_index} with {len(location_list)} stages")
                return None
            
            media_url = location_list[stage_index]
            logger.debug(f"Found media URL for {media_key}: {media_url}")
            return media_url
            
        except Exception as e:
            logger.error(f"Error accessing media for key '{media_key}': {e}")
            return None
    
    async def finish_challenge(self, user: discord.User, challenge: Dict, event_id: str, user_id: str):
        """Complete Pea's Place challenge with celebration"""
        challenge_data = self.db.get_user_challenge_data(event_id, user_id, challenge['name'])
        challenge_data['status'] = 'finished'
        challenge_data['finish_time'] = datetime.datetime.now(datetime.UTC)
        
        # Calculate duration
        start_time = challenge_data.get('start_time')
        if start_time:
            if isinstance(start_time, str):
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            duration = datetime.datetime.now(datetime.UTC) - start_time
            challenge_data['duration'] = duration.total_seconds()
        
        self.db.clear_active_challenge(event_id, user_id)
        self.db.save_database()
        
        # Send completion message with statistics
        evidence_count = len(challenge_data.get('evidence', []))
        duration_str = str(datetime.timedelta(seconds=challenge_data.get('duration', 0)))
        
        completion_message = (
            "🎉 **Congratulations! All Pea's Place locations found!** 🎉\n\n"
            f"⏱️ **Time:** {duration_str}\n"
            f"📸 **Evidence submitted:** {evidence_count} screenshots\n\n"
        )
        
        await self.send_dm_safely(user, completion_message)
        logger.info(f"User {user_id} completed Pea's Place in {duration_str} with {evidence_count} evidence items")        

class ChallengeHandlerFactory:
    """
    Factory class to create appropriate challenge handlers based on challenge type
    This provides a clean interface for getting the right handler for each challenge
    """
    
    def __init__(self, bot, database: Database):
        self.bot = bot
        self.db = database
        self.handlers = {
            'trivia': TriviaHandler(bot, database),
            'speed_run': SpeedRunHandler(bot, database),
            'race': RaceHandler(bot, database),
            'peas_place': PeasPlaceHandler(bot, database)  # Special case
        }
    
    def get_handler(self, challenge: Dict) -> BaseChallengeHandler:
        """Get an appropriate handler for a challenge"""
        # Special case for Pea's Place regardless of type
        if challenge['name'] == 'peas_place':
            return self.handlers['peas_place']
        
        # Use challenge type to determine handler
        challenge_type = challenge.get('type', 'race')
        return self.handlers.get(challenge_type, self.handlers['race'])
