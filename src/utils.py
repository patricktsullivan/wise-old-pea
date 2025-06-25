"""
Utility functions for Wise Old Pea Bot
Handles text processing, validation, and helper functions
"""

import re
import string
import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
import logging

logger = logging.getLogger('wise_old_pea.utils')

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison by removing punctuation and converting to lowercase
    This ensures that user input like "Scape Smarts!" matches "scape smarts"
    """
    return re.sub(r'[^\w\s]', '', text.lower().strip().translate(str.maketrans('','', string.punctuation)))

def parse_duration(duration_str: str) -> datetime.timedelta:
    """
    Parse duration string into datetime.timedelta object
    Supports formats like: '5 minutes', '2 hours', '7 days', '1 week', '2 months'
    """
    logger.debug(f"Parsing duration: '{duration_str}'")
    duration_str = duration_str.lower().strip()
    
    # Parse number and unit using regex
    match = re.match(r'(\d+)\s*(minute|hour|day|week|month)s?', duration_str)
    if not match:
        logger.error(f"Invalid duration format: '{duration_str}'. Expected format: '5 days', '2 hours', etc.")
        raise ValueError("Invalid duration format")
    
    amount = int(match.group(1))
    unit = match.group(2)
    logger.debug(f"Parsed: {amount} {unit}(s)")
    
    # Convert to timedelta based on unit
    if unit == 'minute':
        return datetime.timedelta(minutes=amount)
    elif unit == 'hour':
        return datetime.timedelta(hours=amount)
    elif unit == 'day':
        return datetime.timedelta(days=amount)
    elif unit == 'week':
        return datetime.timedelta(weeks=amount)
    elif unit == 'month':
        return datetime.timedelta(days=amount * 30)  # Approximate month length
    else:
        logger.error(f"Unsupported time unit: {unit}")
        raise ValueError("Unsupported time unit")

def find_challenge_by_name(challenges: List[Dict], name: str) -> Optional[Dict]:
    """
    Find a challenge by its name field (not display_name)
    This is the canonical way to look up challenges for commands
    """
    logger.debug(f"Looking for challenge: '{name}'")
    name_normalized = normalize_text(name)
    
    for challenge in challenges:
        challenge_name_normalized = normalize_text(challenge['name'])
        if challenge_name_normalized == name_normalized:
            logger.debug(f"Found challenge: {challenge['name']}")
            return challenge
    
    logger.debug(f"Challenge '{name}' not found")
    return None

def get_usernames(accounts: Dict, user_id: str, discord_name: str) -> str:
    """
    Get formatted username string showing both Discord and OSRS names
    This provides clear identification in public channels
    """
    osrs_name = None
    
    try:
        user_data = accounts.get(user_id, {})
        osrs_name = user_data.get('osrs_username')
    except Exception as e:
        logger.warning(f"Could not retrieve OSRS username for {discord_name}, {user_id}: {e}")

    if osrs_name:
        return f"*{discord_name}* (**{osrs_name}**)"
    else:
        logger.info(f"No OSRS account found for user {user_id}")
        return f"**{discord_name}**"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to a readable string"""
    delta = datetime.timedelta(seconds=seconds)
    return str(delta)

def parse_list_input(user_input: str) -> List[str]:
    """
    Parse comma-separated or newline-separated list input from user
    Handles various formats users might use for list answers
    """
    items = []
    # Split on commas or newlines, then clean up each item
    for item in re.split(r'[,\n]', user_input):
        cleaned = item.strip()
        if cleaned:
            items.append(cleaned)
    return items

# Answer validation functions for different challenge types
def validate_exact_match(user_input: str, correct_answer: Union[str, int]) -> Tuple[bool, str]:
    """Validate exact match answers (case-insensitive, punctuation-ignored)"""
    user_normalized = normalize_text(user_input)
    correct_normalized = normalize_text(str(correct_answer))
    
    # Also check for single letter answers (like A, B, C, D)
    if re.match(r'^[a-z]\.?$', user_input.lower()) and user_input[0].upper() in str(correct_answer):
        return True, ""
    
    return user_normalized == correct_normalized, ""

def validate_multiple_choice(user_input: str, correct_answer: str, options: List[str]) -> Tuple[bool, str]:
    """Validate multiple choice answers (letter or full text)"""
    user_normalized = normalize_text(user_input)
    correct_normalized = normalize_text(correct_answer)
    
    # Direct text match
    if user_normalized == correct_normalized:
        return True, ""
    
    # Letter choice (A, B, C, D)
    letter_match = re.match(r'^([a-z])\.?$', user_input.lower())
    if letter_match and options:
        letter_index = ord(letter_match.group(1)) - ord('a')
        if 0 <= letter_index < len(options):
            if normalize_text(options[letter_index]) == correct_normalized:
                return True, ""
    
    return False, ""

def extract_letter_answers(user_input: str) -> List[str]:
    """
    Extract all valid letter answers from user input regardless of formatting.
    This function recognizes that users express letter choices in many different ways
    and extracts the meaningful content rather than enforcing rigid format requirements.
    """
    
    # Find all single letters in the input, with optional periods
    # This pattern matches individual letters that appear to be answer choices
    letter_pattern = r'\b([a-zA-Z])\.?\b'
    
    # Extract all letter matches from the input
    letter_matches = re.findall(letter_pattern, user_input.lower())
    
    # Remove duplicates while preserving order
    seen_letters = set()
    unique_letters = []
    for letter in letter_matches:
        if letter not in seen_letters:
            seen_letters.add(letter)
            unique_letters.append(letter)
    
    return unique_letters

def validate_list_exact(user_input: str, correct_answer: List[str], options: List[str] = None) -> Tuple[bool, str]:
    """
    Enhanced list validation that properly handles letter answers in any format.
    This version treats letter parsing as a special case that requires more flexibility
    than general text parsing.
    """

    # First, try to extract letter answers from the input
    extracted_letters = extract_letter_answers(user_input)
    
    user_items_normalized = []
    
    if extracted_letters and options:
        # If we found letters and have options to map them to, process as letter answers
        for letter in extracted_letters:
            letter_index = ord(letter) - ord('a')  # a=0, b=1, c=2, etc.
            
            if 0 <= letter_index < len(options):
                # Valid letter - convert to corresponding option text
                corresponding_option = options[letter_index]
                user_items_normalized.append(normalize_text(corresponding_option))
            else:
                # Invalid letter (like 'z' when only a-j exist)
                return False, f"Invalid option letter: {letter.upper()}"

    else:
        # No valid letters found, fall back to text parsing
        user_items = parse_list_input(user_input)
        user_items_normalized = [normalize_text(item) for item in user_items]
    
    # Rest of validation logic remains the same...
    correct_items_normalized = [normalize_text(answer) for answer in correct_answer]
    
    user_set = set(user_items_normalized)
    correct_set = set(correct_items_normalized)
    
    if user_set == correct_set:
        return True, ""
    
    # Provide helpful feedback about differences
    missing = correct_set - user_set
    extra = user_set - correct_set
    
    feedback_parts = []
    if missing:
        feedback_parts.append(f"Missing: {', '.join(missing)}")
    if extra:
        feedback_parts.append(f"Extra: {', '.join(extra)}")
    
    return False, " | ".join(feedback_parts)

def validate_list_any_count(user_input: str, correct_answer: List[str], min_count: int) -> Tuple[bool, str]:
    """Validate that user provides at least min_count correct items from the list"""
    user_items = [normalize_text(item) for item in parse_list_input(user_input)]
    correct_items = [normalize_text(item) for item in correct_answer]
    
    user_set = set(user_items)
    correct_set = set(correct_items)
    
    valid_answers = user_set.intersection(correct_set)
    invalid_answers = user_set - correct_set
    
    if len(valid_answers) >= min_count and not invalid_answers:
        return True, f"You provided {len(valid_answers)} correct answers!"
    
    feedback = []
    if len(valid_answers) < min_count:
        feedback.append(f"Need at least {min_count} correct answers (you had {len(valid_answers)})")
    if invalid_answers:
        feedback.append(f"Invalid answers: {', '.join(invalid_answers)}")
    
    return False, " | ".join(feedback)

def validate_dictionary_match(user_input: str, correct_answer: Dict[str, str]) -> Tuple[bool, str]:
    """Validate dictionary answers where ALL values must be provided in any order"""

    # Parse user input into individual items
    user_items = parse_list_input(user_input)  # Handles commas, newlines, etc.
    user_items_normalized = [normalize_text(item) for item in user_items]
    
    # Get all required values (normalized)
    required_values = [normalize_text(value) for value in correct_answer.values()]
    
    # Check if user provided all required values
    user_set = set(user_items_normalized)
    required_set = set(required_values)
    
    if user_set == required_set:
        return True, ""
    
    # Provide helpful feedback about what's missing or extra
    missing = required_set - user_set
    extra = user_set - required_set
    
    feedback_parts = []
    if missing:
        feedback_parts.append(f"Missing: {', '.join(missing)}")
    if extra:
        feedback_parts.append(f"Extra: {', '.join(extra)}")
    
    if feedback_parts:
        return False, " | ".join(feedback_parts)
    else:
        return False, f"Expected: {', '.join(correct_answer.values())}"

def validate_ordered_list(user_input: str, correct_answer: str, options: List[str]) -> Tuple[bool, str]:
    """Validate ordered list answers (like D, C, B, A ranking)"""
    user_normalized = normalize_text(user_input)
    correct_normalized = normalize_text(correct_answer)
    
    if user_normalized == correct_normalized:
        return True, ""
    
    # Also check letter sequences
    user_letters = re.findall(r'[a-z]', user_input.lower())
    correct_letters = re.findall(r'[a-z]', correct_answer.lower())
    
    if user_letters == correct_letters:
        return True, ""
    
    return False, f"Expected order: {correct_answer}"

def validate_multiple_acceptable(user_input: str, correct_answer: List[str]) -> Tuple[bool, str]:
    """Validate when multiple different answers are acceptable"""
    user_normalized = normalize_text(user_input)
    
    for acceptable_answer in correct_answer:
        if user_normalized == normalize_text(acceptable_answer):
            return True, ""
    
    return False, ""

def validate_gear_setup(user_input: str, correct_answer: Dict[str, Union[str, List[str]]]) -> Tuple[bool, str]:
    """
    Enhanced gear setup validation that handles multiple input formats
    This version searches for gear pieces within the user's input rather than 
    expecting a specific format, making it much more user-friendly
    """
    from utils import normalize_text
    import re
    
    # Normalize the entire user input for searching
    user_input_normalized = normalize_text(user_input)
    
    # Track which gear slots we've successfully found
    found_gear = {}
    missing_pieces = []
    
    # Process each required gear slot
    for slot, gear in correct_answer.items():
        slot_found = False
        found_item = None
        
        # Handle multiple acceptable options for this slot
        if isinstance(gear, list):
            acceptable_items = [(option, normalize_text(option)) for option in gear]
        else:
            acceptable_items = [(gear, normalize_text(gear))]
        
        # Search for any acceptable item for this slot within the user input
        for original_item, normalized_item in acceptable_items:
            if normalized_item in user_input_normalized:
                slot_found = True
                found_item = original_item
                break
        
        # Record the result for this slot
        if slot_found:
            found_gear[slot] = found_item
        else:
            missing_pieces.append(f"{slot}: {gear}")
    
    # Check for success
    if len(missing_pieces) == 0:
        return True, ""
    
    # Provide helpful feedback about what was found and what's missing
    feedback_parts = []
    if found_gear:
        found_items = [f"{slot}: {item}" for slot, item in found_gear.items()]
        feedback_parts.append(f"Found: {', '.join(found_items)}")
    
    if missing_pieces:
        feedback_parts.append(f"Missing: {', '.join(missing_pieces)}")
    
    return False, " | ".join(feedback_parts)

def validate_answer(user_answer: str, correct_answer: Any, answer_type: str, question_data: Dict) -> Tuple[bool, str]:
    """
    Main answer validation function that routes to specific validators
    This is the entry point for all answer checking
    """
    user_input = user_answer.strip()
    
    # Route to appropriate validator based on answer type
    if answer_type == 'exact_match':
        return validate_exact_match(user_input, correct_answer)
    elif answer_type == 'multiple_choice':
        return validate_multiple_choice(user_input, correct_answer, question_data.get('o', []))
    elif answer_type == 'list_exact':
        return validate_list_exact(user_input, correct_answer, question_data.get('o', []))
    elif answer_type == 'list_any_count':
        min_count = question_data.get('min_count', 3)
        return validate_list_any_count(user_input, correct_answer, min_count)
    elif answer_type == 'list_all_required':
        return validate_list_exact(user_input, correct_answer, question_data.get('o', []))  # Same as exact
    elif answer_type == 'dictionary_match':
        return validate_dictionary_match(user_input, correct_answer)
    elif answer_type == 'ordered_list':
        return validate_ordered_list(user_input, correct_answer, question_data.get('o', []))
    elif answer_type == 'multiple_acceptable':
        return validate_multiple_acceptable(user_input, correct_answer)
    elif answer_type == 'gear_setup':
        return validate_gear_setup(user_input, correct_answer)
    else:
        # Legacy validation for backward compatibility
        return validate_legacy(user_input, correct_answer)

def validate_legacy(user_input: str, correct_answer: Any) -> Tuple[bool, str]:
    """Legacy validation for backward compatibility with old question formats"""
    user_normalized = normalize_text(user_input)
    
    if isinstance(correct_answer, list):
        for ans in correct_answer:
            if user_normalized == normalize_text(str(ans)):
                return True, ""
    elif isinstance(correct_answer, dict):
        for key, value in correct_answer.items():
            if user_normalized == normalize_text(str(value)):
                return True, ""
    else:
        if user_normalized == normalize_text(str(correct_answer)):
            return True, ""
        # Check for letter answers
        if re.match(r'^[a-z]\.?$', user_input.lower()) and user_input[0].upper() in str(correct_answer):
            return True, ""
    
    return False, ""

def format_correct_answer(correct_answer: Any, answer_type: str) -> str:
    """Format the correct answer for display to users"""
    if answer_type == 'list_any_count':
        return f"Any {len(correct_answer)} from: {', '.join(correct_answer)}"
    elif answer_type == 'dictionary_match':
        return ', '.join([f"{k}: {v}" for k, v in correct_answer.items()])
    elif answer_type == 'gear_setup':
        formatted = []
        for slot, gear in correct_answer.items():
            if isinstance(gear, list):
                formatted.append(f"{slot}: {' or '.join(gear)}")
            else:
                formatted.append(f"{slot}: {gear}")
        return '\n'.join(formatted)
    elif isinstance(correct_answer, list):
        return ', '.join(map(str, correct_answer))
    else:
        return str(correct_answer)

def calculate_trivia_score(challenge_data: Dict) -> int:
    """Calculate total number of correct trivia answers"""
    trivia_answers = challenge_data.get('trivia_answers', {})
    correct_count = 0
    
    for stage, answer_data in trivia_answers.items():
        if answer_data.get('correct', False):
            correct_count += 1
    
    return correct_count

def is_event_ended(event_info: Dict) -> bool:
    """Check if an event has ended based on current time"""
    end_time = event_info.get('end_time')
    if isinstance(end_time, str):
        end_time = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    
    current_time = datetime.datetime.now(datetime.UTC)
    return current_time >= end_time if end_time else False