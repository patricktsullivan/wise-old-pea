# database.py - Enhanced database with backup and validation
import json
import os
import shutil
import datetime
from typing import Dict, Any, Optional, List
import logging
from config import DATA_DIRECTORY, EVENTS_FILE, ACCOUNTS_FILE, BACKUP_DIRECTORY

logger = logging.getLogger(__name__)

class EventDatabase:
    """Enhanced JSON-based database with backup and validation"""
    
    def __init__(self, data_dir: str = DATA_DIRECTORY):
        self.data_dir = data_dir
        self.events_file = os.path.join(data_dir, EVENTS_FILE)
        self.accounts_file = os.path.join(data_dir, ACCOUNTS_FILE)
        self.backup_dir = BACKUP_DIRECTORY
        
        # Ensure directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Load data
        self.events_data = self._load_file(self.events_file, {})
        self.accounts_data = self._load_file(self.accounts_file, {})
    
    def _load_file(self, filepath: str, default: Any) -> Any:
        """Load data from JSON file with error handling"""
        if not os.path.exists(filepath):
            logger.info(f"File {filepath} not found, starting with empty data")
            return default
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded data from {filepath}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {filepath}: {e}")
            # Try to load backup
            backup_file = self._get_latest_backup(filepath)
            if backup_file:
                logger.info(f"Attempting to restore from backup: {backup_file}")
                return self._load_file(backup_file, default)
            return default
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return default
    
    def _save_file(self, filepath: str, data: Any, create_backup: bool = True) -> bool:
        """Save data to JSON file with backup creation"""
        try:
            # Create backup before saving
            if create_backup and os.path.exists(filepath):
                self._create_backup(filepath)
            
            # Save to temporary file first
            temp_file = filepath + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            
            # Atomically replace the original file
            shutil.move(temp_file, filepath)
            logger.debug(f"Saved data to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
            # Clean up temp file if it exists
            if os.path.exists(filepath + '.tmp'):
                os.remove(filepath + '.tmp')
            return False
    
    def _create_backup(self, filepath: str):
        """Create timestamped backup of file"""
        if not os.path.exists(filepath):
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(filepath)
        backup_name = f"{filename}.{timestamp}.backup"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            shutil.copy2(filepath, backup_path)
            logger.debug(f"Created backup: {backup_path}")
            
            # Clean up old backups (keep last 10)
            self._cleanup_old_backups(filename)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
    
    def _cleanup_old_backups(self, base_filename: str, keep_count: int = 10):
        """Remove old backup files, keeping only the most recent"""
        try:
            backup_files = []
            for file in os.listdir(self.backup_dir):
                if file.startswith(base_filename) and file.endswith('.backup'):
                    backup_path = os.path.join(self.backup_dir, file)
                    backup_files.append((os.path.getmtime(backup_path), backup_path))
            
            # Sort by modification time and remove oldest
            backup_files.sort(reverse=True)
            for _, backup_path in backup_files[keep_count:]:
                os.remove(backup_path)
                logger.debug(f"Removed old backup: {backup_path}")
                
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
    
    def _get_latest_backup(self, filepath: str) -> Optional[str]:
        """Get the most recent backup file"""
        filename = os.path.basename(filepath)
        latest_backup = None
        latest_time = 0
        
        try:
            for file in os.listdir(self.backup_dir):
                if file.startswith(filename) and file.endswith('.backup'):
                    backup_path = os.path.join(self.backup_dir, file)
                    backup_time = os.path.getmtime(backup_path)
                    if backup_time > latest_time:
                        latest_time = backup_time
                        latest_backup = backup_path
        except Exception as e:
            logger.error(f"Error finding latest backup: {e}")
        
        return latest_backup
    
    def validate_data(self) -> List[str]:
        """Validate data integrity and return list of issues"""
        issues = []
        
        # Validate events data structure
        if not isinstance(self.events_data, dict):
            issues.append("Events data is not a dictionary")
        else:
            for event_id, event_data in self.events_data.items():
                if not isinstance(event_data, dict):
                    issues.append(f"Event {event_id} data is not a dictionary")
                    continue
                
                required_fields = ['id', 'name', 'event_type', 'creator_id', 'guild_id']
                for field in required_fields:
                    if field not in event_data:
                        issues.append(f"Event {event_id} missing required field: {field}")
        
        # Validate accounts data structure
        if not isinstance(self.accounts_data, dict):
            issues.append("Accounts data is not a dictionary")
        else:
            for discord_id, account_data in self.accounts_data.items():
                if not isinstance(account_data, dict):
                    issues.append(f"Account {discord_id} data is not a dictionary")
                    continue
                
                required_fields = ['discord_id', 'username']
                for field in required_fields:
                    if field not in account_data:
                        issues.append(f"Account {discord_id} missing required field: {field}")
        
        return issues
    
    # Event operations
    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get event by ID"""
        return self.events_data.get(event_id)
    
    def save_event(self, event_id: str, event_data: Dict) -> bool:
        """Save event data"""
        try:
            self.events_data[event_id] = event_data
            return self._save_file(self.events_file, self.events_data)
        except Exception as e:
            logger.error(f"Error saving event {event_id}: {e}")
            return False
    
    def get_all_events(self) -> Dict[str, Dict]:
        """Get all events"""
        return self.events_data.copy()
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event"""
        if event_id in self.events_data:
            try:
                del self.events_data[event_id]
                return self._save_file(self.events_file, self.events_data)
            except Exception as e:
                logger.error(f"Error deleting event {event_id}: {e}")
                return False
        return True
    
    def get_events_by_guild(self, guild_id: int) -> Dict[str, Dict]:
        """Get all events for a specific guild"""
        guild_events = {}
        for event_id, event_data in self.events_data.items():
            if event_data.get('guild_id') == guild_id:
                guild_events[event_id] = event_data
        return guild_events
    
    def get_active_events(self) -> Dict[str, Dict]:
        """Get all active events"""
        active_events = {}
        for event_id, event_data in self.events_data.items():
            if event_data.get('status') == 'active':
                active_events[event_id] = event_data
        return active_events
    
    # Account operations
    def get_account(self, discord_id: int) -> Optional[Dict]:
        """Get OSRS account by Discord ID"""
        return self.accounts_data.get(str(discord_id))
    
    def save_account(self, discord_id: int, account_data: Dict) -> bool:
        """Save OSRS account data"""
        try:
            self.accounts_data[str(discord_id)] = account_data
            return self._save_file(self.accounts_file, self.accounts_data)
        except Exception as e:
            logger.error(f"Error saving account {discord_id}: {e}")
            return False
    
    def get_all_accounts(self) -> Dict[str, Dict]:
        """Get all OSRS accounts"""
        return self.accounts_data.copy()
    
    def delete_account(self, discord_id: int) -> bool:
        """Delete an OSRS account"""
        discord_id_str = str(discord_id)
        if discord_id_str in self.accounts_data:
            try:
                del self.accounts_data[discord_id_str]
                return self._save_file(self.accounts_file, self.accounts_data)
            except Exception as e:
                logger.error(f"Error deleting account {discord_id}: {e}")
                return False
        return True
    
    def get_account_by_username(self, username: str) -> Optional[Dict]:
        """Get account by OSRS username"""
        for account_data in self.accounts_data.values():
            if account_data.get('username', '').lower() == username.lower():
                return account_data
        return None
    
    # Bulk operations
    def save_all_data(self) -> bool:
        """Save all data files"""
        events_saved = self._save_file(self.events_file, self.events_data)
        accounts_saved = self._save_file(self.accounts_file, self.accounts_data)
        return events_saved and accounts_saved
    
    def export_data(self, export_dir: str) -> bool:
        """Export all data to specified directory"""
        try:
            os.makedirs(export_dir, exist_ok=True)
            
            export_events = os.path.join(export_dir, EVENTS_FILE)
            export_accounts = os.path.join(export_dir, ACCOUNTS_FILE)
            
            events_exported = self._save_file(export_events, self.events_data, create_backup=False)
            accounts_exported = self._save_file(export_accounts, self.accounts_data, create_backup=False)
            
            return events_exported and accounts_exported
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        total_events = len(self.events_data)
        active_events = len([e for e in self.events_data.values() if e.get('status') == 'active'])
        total_accounts = len(self.accounts_data)
        
        # Event type breakdown
        event_types = {}
        for event_data in self.events_data.values():
            event_type = event_data.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            'total_events': total_events,
            'active_events': active_events,
            'completed_events': total_events - active_events,
            'total_accounts': total_accounts,
            'event_types': event_types,
            'data_files': {
                'events_file_size': os.path.getsize(self.events_file) if os.path.exists(self.events_file) else 0,
                'accounts_file_size': os.path.getsize(self.accounts_file) if os.path.exists(self.accounts_file) else 0
            }
        }