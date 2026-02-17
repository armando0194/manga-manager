import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

class Database:
    """SQLite database for tracking processed manga files."""
    
    def __init__(self, db_path='/data/manga_manager.db'):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _create_tables(self):
        """Create database schema if not exists."""
        cursor = self.conn.cursor()
        
        # Processed files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                series TEXT NOT NULL,
                volume INTEGER,
                chapter REAL,
                file_path TEXT,
                cover_path TEXT,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash TEXT UNIQUE,
                status TEXT DEFAULT 'completed',
                error_message TEXT
            )
        ''')
        
        # Create indexes for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_series_volume 
            ON processed_files(series, volume)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_hash 
            ON processed_files(file_hash)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status 
            ON processed_files(status)
        ''')
        
        self.conn.commit()
    
    def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def is_duplicate(self, file_hash):
        """Check if file hash already exists in database."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM processed_files WHERE file_hash = ?', (file_hash,))
        return cursor.fetchone() is not None
    
    def add_processed_file(self, filename, series, volume, chapter, file_path, 
                          cover_path, file_hash, status='completed', error_message=None):
        """Add processed file to database."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO processed_files 
            (filename, series, volume, chapter, file_path, cover_path, file_hash, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (filename, series, volume, chapter, file_path, cover_path, file_hash, status, error_message))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_files_by_series(self, series, status=None):
        """Get all processed files for a series."""
        cursor = self.conn.cursor()
        if status:
            cursor.execute('''
                SELECT * FROM processed_files 
                WHERE series = ? AND status = ?
                ORDER BY volume, chapter
            ''', (series, status))
        else:
            cursor.execute('''
                SELECT * FROM processed_files 
                WHERE series = ?
                ORDER BY volume, chapter
            ''', (series,))
        return cursor.fetchall()
    
    def get_volume_cover(self, series, volume):
        """Get cover path for a specific volume."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT cover_path FROM processed_files 
            WHERE series = ? AND volume = ? AND cover_path IS NOT NULL
            LIMIT 1
        ''', (series, volume))
        result = cursor.fetchone()
        return result['cover_path'] if result else None
    
    def get_files_needing_review(self):
        """Get all files with status 'needs_review'."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM processed_files 
            WHERE status = 'needs_review'
            ORDER BY processed_date DESC
        ''')
        return cursor.fetchall()
    
    def update_status(self, file_id, status, error_message=None):
        """Update file processing status."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE processed_files 
            SET status = ?, error_message = ?
            WHERE id = ?
        ''', (status, error_message, file_id))
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
