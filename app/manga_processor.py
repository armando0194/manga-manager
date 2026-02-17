#!/usr/bin/env python3
"""
Manga Manager - Main Processing Application

Monitors download directory for new CBZ files and processes them through
a complete pipeline from downloads to final library.
"""

import time
import signal
import shutil
import threading
from pathlib import Path

from config import Config
from database import Database
from file_watcher import FileWatcher
from file_renamer import FileRenamer
from cover_manager import CoverManager
from web_ui import WebUI
from utils import setup_logging, ensure_directory

class MangaManager:
    """Main application coordinator - integrates all components."""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logging(self.config.log_level, '/logs/processor.log')
        self.db = Database()
        self.running = True
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("Manga Manager started")
        self._initialize_directories()
        
        # Initialize processors
        manga_path = self.config.paths.get('manga', '/manga')
        covers_path = Path(self.config.paths.get('data', '/data')) / 'covers'
        
        self.file_renamer = FileRenamer(
            manga_library_path=manga_path,
            volume_digits=self.config.naming.get('volume_digits', 3),
            chapter_digits=self.config.naming.get('chapter_digits', 5)
        )
        
        self.cover_manager = CoverManager(covers_cache_path=covers_path, database=self.db)
        
        downloads_path = self.config.paths.get('downloads', '/downloads')
        self.file_watcher = FileWatcher(
            watch_path=downloads_path,
            callback=self.process_file,
            debounce_seconds=2
        )
        
        self.web_ui = WebUI(self.config, self.db, self.cover_manager, self.file_renamer)
        self.logger.info("All components initialized")
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _initialize_directories(self):
        paths = self.config.paths
        data_dir = Path(paths.get('data', '/data'))
        ensure_directory(data_dir / 'covers')
        processing_dir = Path(paths.get('processing', '/processing'))
        ensure_directory(processing_dir / 'failed')
        self.logger.info("Directory structure initialized")
    
    def process_file(self, file_path: Path):
        """Complete processing pipeline for a CBZ file."""
        self.logger.info(f"{'='*80}\nStarting processing: {file_path.name}\n{'='*80}")
        
        try:
            # Duplicate check
            file_hash = self.db.calculate_file_hash(file_path)
            if self.db.is_duplicate(file_hash):
                self.logger.warning(f"Duplicate: {file_path.name}")
                self._move_to_failed(file_path, "Duplicate file")
                return
            
            self.logger.info(f"Hash: {file_hash[:16]}...")
            
            # Move to processing
            processing_path = self._move_to_processing(file_path)
            if not processing_path:
                return
            
            # Analyze and rename
            self.logger.info("Analyzing metadata...")
            rename_result = self.file_renamer.process_file(
                processing_path, dest_dir=None,
                update_metadata=self.config.metadata.get('preserve_existing', True),
                preserve_existing=True
            )
            
            if rename_result['needs_review']:
                self.logger.warning(f"Needs review: {', '.join(rename_result['issues'])}")
                self._mark_for_review(processing_path, rename_result, file_hash)
                return
            
            current_path = rename_result['new_path']
            analysis = rename_result['analysis']
            self.logger.info(f"Detected: {analysis['series']} Vol.{analysis['volume']} Ch.{analysis['chapter']}")
            
            # Process cover
            self.logger.info("Processing cover...")
            cover_result = self.cover_manager.process_cover(
                current_path, analysis['series'], analysis['volume'], analysis['chapter']
            )
            
            if cover_result['needs_review']:
                self.logger.warning(f"Cover issue: {cover_result['message']}")
                self._mark_for_review(current_path, rename_result, file_hash, cover_result['message'])
                return
            
            self.logger.info(f"Cover: {cover_result['message']}")
            
            # Move to library
            final_path = self._move_to_library(current_path, analysis['series'])
            if not final_path:
                self._mark_for_review(current_path, rename_result, file_hash, "Move failed")
                return
            
            # Backup if enabled
            if self.config.processing.get('backup_enabled', False):
                self._create_backup(final_path, analysis['series'])
            
            # Record success
            self.db.add_processed_file(
                filename=file_path.name, series=analysis['series'],
                volume=analysis['volume'], chapter=analysis['chapter'],
                file_path=str(final_path),
                cover_path=str(cover_result.get('cover_path')) if cover_result.get('cover_path') else None,
                file_hash=file_hash, status='completed'
            )
            
            self.logger.info(f"✓ Success: {final_path.name}\n✓ Location: {final_path}")
            
        except Exception as e:
            self.logger.error(f"Error: {file_path.name}: {e}", exc_info=True)
            self._move_to_failed(file_path, str(e))
    
    def _move_to_processing(self, file_path: Path):
        try:
            processing_dir = Path(self.config.paths.get('processing', '/processing'))
            ensure_directory(processing_dir)
            dest_path = processing_dir / file_path.name
            
            if dest_path.exists():
                base, suffix, counter = dest_path.stem, dest_path.suffix, 1
                while dest_path.exists():
                    dest_path = processing_dir / f"{base}_{counter}{suffix}"
                    counter += 1
            
            shutil.move(str(file_path), str(dest_path))
            self.logger.info(f"→ Processing: {dest_path.name}")
            return dest_path
        except Exception as e:
            self.logger.error(f"Move to processing failed: {e}")
            return None
    
    def _move_to_library(self, file_path: Path, series: str):
        try:
            manga_dir = Path(self.config.paths.get('manga', '/manga'))
            series_dir = manga_dir / series
            ensure_directory(series_dir)
            dest_path = series_dir / file_path.name
            
            if dest_path.exists():
                self.logger.warning(f"Already exists: {dest_path.name}")
                return None
            
            shutil.move(str(file_path), str(dest_path))
            self.logger.info(f"→ Library: {dest_path}")
            return dest_path
        except Exception as e:
            self.logger.error(f"Move to library failed: {e}")
            return None
    
    def _create_backup(self, file_path: Path, series: str):
        try:
            backup_dir = Path(self.config.paths.get('processing', '/processing')) / series
            ensure_directory(backup_dir)
            shutil.copy2(str(file_path), str(backup_dir / file_path.name))
            self.logger.info(f"Backup created")
        except Exception as e:
            self.logger.warning(f"Backup failed: {e}")
    
    def _move_to_failed(self, file_path: Path, reason: str):
        try:
            failed_dir = Path(self.config.paths.get('processing', '/processing')) / 'failed'
            ensure_directory(failed_dir)
            dest_path = failed_dir / file_path.name
            
            if dest_path.exists():
                base, suffix, counter = dest_path.stem, dest_path.suffix, 1
                while dest_path.exists():
                    dest_path = failed_dir / f"{base}_{counter}{suffix}"
                    counter += 1
            
            if file_path.exists():
                shutil.move(str(file_path), str(dest_path))
                self.logger.info(f"→ Failed: {dest_path.name}")
            
            file_hash = self.db.calculate_file_hash(dest_path)
            self.db.add_processed_file(
                filename=file_path.name, series=None, volume=None, chapter=None,
                file_path=str(dest_path), cover_path=None,
                file_hash=file_hash, status='failed', error_message=reason
            )
        except Exception as e:
            self.logger.error(f"Move to failed failed: {e}")
    
    def _mark_for_review(self, file_path: Path, rename_result: dict, file_hash: str, extra_message: str = None):
        try:
            analysis = rename_result['analysis']
            issues = rename_result['issues'].copy()
            if extra_message:
                issues.append(extra_message)
            
            self.db.add_processed_file(
                filename=file_path.name,
                series=analysis.get('series'), volume=analysis.get('volume'),
                chapter=analysis.get('chapter'), file_path=str(file_path),
                cover_path=None, file_hash=file_hash,
                status='needs_review', error_message='; '.join(issues)
            )
            
            self.logger.warning(f"Marked for review: {file_path.name}")
        except Exception as e:
            self.logger.error(f"Mark for review failed: {e}")
    
    def run(self):
        """Main application loop."""
        check_interval = self.config.check_interval
        self.logger.info(f"Starting (check interval: {check_interval}s)")
        
        self.file_watcher.start()
        self.file_watcher.scan_existing_files()
        
        web_thread = threading.Thread(
            target=self.web_ui.run,
            kwargs={'host': '0.0.0.0', 'port': 8080, 'debug': False},
            daemon=True
        )
        web_thread.start()
        self.logger.info("Web UI: http://0.0.0.0:8080")
        
        while self.running:
            try:
                self.file_watcher.check_pending()
                time.sleep(check_interval)
            except Exception as e:
                self.logger.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(check_interval)
        
        self._shutdown()
    
    def _shutdown(self):
        self.logger.info("Shutting down...")
        self.file_watcher.stop()
        self.db.close()
        self.logger.info("Stopped")

if __name__ == '__main__':
    manager = MangaManager()
    manager.run()
