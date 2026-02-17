import yaml
import os
from pathlib import Path

class Config:
    """Configuration loader for manga-manager settings."""
    
    def __init__(self, config_path='/config/settings.yml'):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get(self, *keys, default=None):
        """Get nested configuration value.
        
        Example:
            config.get('general', 'log_level')
            config.get('paths', 'downloads')
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value
    
    @property
    def log_level(self):
        return self.get('general', 'log_level', default='INFO')
    
    @property
    def check_interval(self):
        return self.get('general', 'check_interval', default=30)
    
    @property
    def paths(self):
        return self.get('paths', default={})
    
    @property
    def processing(self):
        return self.get('processing', default={})
    
    @property
    def naming(self):
        return self.get('naming', default={})
    
    @property
    def metadata(self):
        return self.get('metadata', default={})
