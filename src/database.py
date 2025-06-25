"""
Database operations and data persistence for Wise Old Pea Bot
Handles all JSON file operations and data structure management
"""

import json
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger('wise_old_pea.database')

class Database:
    """Handles all database operations for the bot"""
    
    def __init__(self, data_dir: Path = None):
        """Initialize database with data directory"""
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.database_file = self.data_dir / "wise_old_pea_data.json"
        
        # Initialize data structures
        self.accounts = {}
        self.events = {}
        
        self.load_database()
    
    def load_database(self):
        """Load data from JSON database file"""
        try:
            logger.info(f"Loading database from {self.database_file}")
            with open(self.database_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.accounts = data.get('accounts', {})
                self.events = data.get('events', {})
            logger.info(f"Database loaded successfully: {len(self.accounts)} accounts, {len(self.events)} events")
        except FileNotFoundError:
            logger.warning(f"Database file {self.database_file} not found, starting with empty database")
            self.accounts = {}
            self.events = {}
        except Exception as e:
            logger.error(f"Error loading database: {e}")
            logger.info("Starting with empty database")
            self.accounts = {}
            self.events = {}
    
    def save_database(self):
        """Save data to JSON database file"""
        try:
            logger.debug("Saving database...")
            data = {
                'accounts': self.accounts,
                'events': self.events
            }
            with open(self.database_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            logger.debug("Database saved successfully")
        except Exception as e:
            logger.error(f"Error saving database: {e}")
    
    # Account operations
    def link_account(self, user_id: str, discord_name: str, osrs_username: str):
        """Link a Discord account to an OSRS username"""
        self.accounts[user_id] = {
            'discord_name': discord_name,
            'discord_id': user_id,
            'osrs_username': osrs_username,
            'linked_at': datetime.datetime.now(datetime.UTC)
        }
        self.save_database()
        logger.info(f"Linked {discord_name} to OSRS account: {osrs_username}")
    
    def get_account(self, user_id: str) -> Optional[Dict]:
        """Get account information for a user"""
        return self.accounts.get(user_id)
    
    def find_user_by_name(self, name: str) -> Optional[str]:
        """Find user ID by Discord name or OSRS username"""
        name_lower = name.lower()
        for user_id, account in self.accounts.items():
            if (account['discord_name'].lower() == name_lower or 
                account['osrs_username'].lower() == name_lower):
                return user_id
        return None
    
    # Event operations
    def create_event(self, event_data: Dict) -> str:
        """Create a new event and return its ID"""
        event_id = f"event_{len(self.events) + 1}_{int(datetime.datetime.now(datetime.UTC).timestamp())}"
        self.events[event_id] = event_data
        self.save_database()
        logger.info(f"Created event {event_id}: {event_data.get('info', {}).get('name', 'Unknown')}")
        return event_id
    
    def get_active_event(self) -> Optional[str]:
        """Get the currently active event ID"""
        for event_id, event_data in self.events.items():
            if event_data.get('info', {}).get('status') == 'active':
                return event_id
        return None
    
    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get event data by ID"""
        return self.events.get(event_id)
    
    def update_event(self, event_id: str, updates: Dict):
        """Update event data"""
        if event_id in self.events:
            # Deep merge the updates
            self._deep_update(self.events[event_id], updates)
            self.save_database()
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """Recursively update nested dictionaries"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    # User challenge operations
    def get_user_challenge_data(self, event_id: str, user_id: str, challenge_name: str) -> Dict:
        """Get user's challenge data, creating structure if needed"""
        if event_id not in self.events:
            self.events[event_id] = {'info': {}, 'users': {}}
        if 'users' not in self.events[event_id]:
            self.events[event_id]['users'] = {}
        if user_id not in self.events[event_id]['users']:
            self.events[event_id]['users'][user_id] = {}
        if challenge_name not in self.events[event_id]['users'][user_id]:
            self.events[event_id]['users'][user_id][challenge_name] = {
                'status': 'not_started',
                'evidence': []
            }
        return self.events[event_id]['users'][user_id][challenge_name]
    
    def set_active_challenge(self, event_id: str, user_id: str, challenge_name: str):
        """Set user's active challenge"""
        if event_id not in self.events:
            self.events[event_id] = {'info': {}, 'users': {}}
        if 'users' not in self.events[event_id]:
            self.events[event_id]['users'] = {}
        if user_id not in self.events[event_id]['users']:
            self.events[event_id]['users'][user_id] = {}
        
        self.events[event_id]['users'][user_id]['active_challenge'] = challenge_name
        self.save_database()
    
    def get_active_challenge(self, event_id: str, user_id: str) -> Optional[str]:
        """Get user's active challenge"""
        return self.events.get(event_id, {}).get('users', {}).get(user_id, {}).get('active_challenge')
    
    def clear_active_challenge(self, event_id: str, user_id: str):
        """Clear user's active challenge"""
        if (event_id in self.events and 
            'users' in self.events[event_id] and 
            user_id in self.events[event_id]['users'] and
            'active_challenge' in self.events[event_id]['users'][user_id]):
            del self.events[event_id]['users'][user_id]['active_challenge']
            self.save_database()
    
    def add_user_to_event(self, event_id: str, user_id: str):
        """Add a user to an event"""
        if event_id not in self.events:
            self.events[event_id] = {'info': {}, 'users': {}}
        if 'users' not in self.events[event_id]:
            self.events[event_id]['users'] = {}
        if user_id not in self.events[event_id]['users']:
            self.events[event_id]['users'][user_id] = {
                'joined_at': datetime.datetime.now(datetime.UTC)
            }
        self.save_database()
    
    def is_user_in_event(self, event_id: str, user_id: str) -> bool:
        """Check if user is in an event"""
        return user_id in self.events.get(event_id, {}).get('users', {})
    
    def get_user_event_data(self, event_id: str, user_id: str) -> Dict:
        """Get all user data for an event"""
        return self.events.get(event_id, {}).get('users', {}).get(user_id, {})