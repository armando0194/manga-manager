import shutil
from pathlib import Path
from typing import Optional, Tuple
import logging

from cbz_utils import CBZFile
from metadata_handler import ComicInfo
from filename_parser import FilenameParser, SeriesDetector

logger = logging.getLogger('manga-manager.renamer')

class FileRenamer:
    """Handles renaming and moving manga files with standardization."""
    
    def __init__(self, manga_library_path: Path, volume_digits: int = 3, chapter_digits: int = 5):
        """
        Args:
            manga_library_path: Path to manga library
            volume_digits: Number of digits for volume padding
            chapter_digits: Number of digits for chapter padding
        """
        self.library_path = Path(manga_library_path)
        self.volume_digits = volume_digits
        self.chapter_digits = chapter_digits
        
        self.parser = FilenameParser()
        self.series_detector = SeriesDetector(manga_library_path)
    
    def analyze_file(self, cbz_path: Path) -> dict:
        """Analyze CBZ file and extract all available metadata.
        
        Args:
            cbz_path: Path to CBZ file
        
        Returns:
            Dictionary with metadata from filename and ComicInfo.xml
        """
        result = {
            'filename_parsed': {},
            'comicinfo_data': {},
            'series': None,
            'volume': None,
            'chapter': None,
            'needs_review': False,
            'issues': []
        }
        
        # Parse filename
        filename_data = self.parser.parse(cbz_path.name)
        result['filename_parsed'] = filename_data
        
        # Try to read ComicInfo.xml
        try:
            cbz = CBZFile(cbz_path)
            if cbz.has_file('ComicInfo.xml'):
                xml_content = cbz.read_file('ComicInfo.xml')
                comic_info = ComicInfo(xml_content)
                result['comicinfo_data'] = {
                    'series': comic_info.series,
                    'volume': comic_info.volume,
                    'number': comic_info.number,
                    'title': comic_info.title
                }
        except Exception as e:
            logger.warning(f"Could not read ComicInfo.xml from {cbz_path.name}: {e}")
            result['issues'].append(f"ComicInfo.xml read error: {e}")
        
        # Determine best values (prefer ComicInfo.xml, fallback to filename)
        result['series'] = result['comicinfo_data'].get('series') or filename_data.get('series')
        result['volume'] = result['comicinfo_data'].get('volume') or filename_data.get('volume')
        result['chapter'] = result['comicinfo_data'].get('number') or filename_data.get('chapter')
        
        # Validate we have minimum required data
        if not result['series']:
            result['needs_review'] = True
            result['issues'].append("Cannot determine series name")
        
        if result['chapter'] is None:
            result['needs_review'] = True
            result['issues'].append("Cannot determine chapter number")
        
        # Try to match series against library
        if result['series']:
            matched = self.series_detector.find_series_match(result['series'])
            if matched:
                result['series'] = matched
                logger.info(f"Matched series '{filename_data.get('series')}' to existing '{matched}'")
        
        return result
    
    def generate_standard_filename(self, series: str, volume: Optional[int], 
                                   chapter: float) -> str:
        """Generate standardized filename.
        
        Args:
            series: Series name
            volume: Volume number (can be None)
            chapter: Chapter number
        
        Returns:
            Standardized filename with .cbz extension
        """
        standardized = self.parser.standardize_filename(
            series, volume, chapter,
            self.volume_digits, self.chapter_digits
        )
        return f"{standardized}.cbz"
    
    def rename_file(self, cbz_path: Path, dest_dir: Optional[Path] = None, 
                   dry_run: bool = False) -> Tuple[bool, Path, list]:
        """Rename CBZ file to standardized format.
        
        Args:
            cbz_path: Path to CBZ file to rename
            dest_dir: Destination directory (if None, renames in place)
            dry_run: If True, don't actually rename, just return what would happen
        
        Returns:
            Tuple of (success, new_path, issues)
        """
        analysis = self.analyze_file(cbz_path)
        
        if analysis['needs_review']:
            logger.warning(f"File needs review: {cbz_path.name}")
            logger.warning(f"Issues: {', '.join(analysis['issues'])}")
            return False, cbz_path, analysis['issues']
        
        # Generate new filename
        new_filename = self.generate_standard_filename(
            analysis['series'],
            analysis['volume'],
            analysis['chapter']
        )
        
        # Determine destination path
        if dest_dir:
            dest_dir = Path(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            new_path = dest_dir / new_filename
        else:
            new_path = cbz_path.parent / new_filename
        
        # Check if file would overwrite itself
        if cbz_path.resolve() == new_path.resolve():
            logger.info(f"File already has correct name: {cbz_path.name}")
            return True, new_path, []
        
        # Check if destination exists
        if new_path.exists() and not dry_run:
            issue = f"Destination already exists: {new_filename}"
            logger.error(issue)
            return False, cbz_path, [issue]
        
        if dry_run:
            logger.info(f"DRY RUN: Would rename '{cbz_path.name}' -> '{new_filename}'")
            return True, new_path, []
        
        # Perform rename/move
        try:
            shutil.move(str(cbz_path), str(new_path))
            logger.info(f"Renamed: '{cbz_path.name}' -> '{new_filename}'")
            return True, new_path, []
        except Exception as e:
            issue = f"Rename failed: {e}"
            logger.error(issue)
            return False, cbz_path, [issue]
    
    def update_metadata(self, cbz_path: Path, series: str, volume: Optional[int], 
                       chapter: float, preserve_existing: bool = True) -> bool:
        """Update ComicInfo.xml metadata in CBZ file.
        
        Args:
            cbz_path: Path to CBZ file
            series: Series name
            volume: Volume number
            chapter: Chapter number
            preserve_existing: If True, only update missing fields
        
        Returns:
            True if successful
        """
        try:
            cbz = CBZFile(cbz_path)
            
            # Read existing ComicInfo.xml or create new
            if cbz.has_file('ComicInfo.xml'):
                xml_content = cbz.read_file('ComicInfo.xml')
                comic_info = ComicInfo(xml_content)
                logger.debug(f"Updating existing ComicInfo.xml in {cbz_path.name}")
            else:
                comic_info = ComicInfo()
                logger.debug(f"Creating new ComicInfo.xml in {cbz_path.name}")
            
            # Update fields (respect preserve_existing)
            if not preserve_existing or not comic_info.series:
                comic_info.series = series
            
            if not preserve_existing or comic_info.volume is None:
                if volume is not None:
                    comic_info.volume = volume
            
            if not preserve_existing or comic_info.number is None:
                comic_info.number = chapter
            
            # Write back to CBZ
            xml_bytes = comic_info.to_xml()
            cbz.add_or_update_file('ComicInfo.xml', xml_bytes)
            
            logger.info(f"Updated metadata in {cbz_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update metadata in {cbz_path.name}: {e}")
            return False
    
    def process_file(self, cbz_path: Path, dest_dir: Optional[Path] = None,
                    update_metadata: bool = True, preserve_existing: bool = True) -> dict:
        """Complete processing: analyze, rename, and update metadata.
        
        Args:
            cbz_path: Path to CBZ file
            dest_dir: Destination directory for renamed file
            update_metadata: Whether to update ComicInfo.xml
            preserve_existing: Whether to preserve existing metadata fields
        
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'original_path': cbz_path,
            'new_path': cbz_path,
            'analysis': {},
            'renamed': False,
            'metadata_updated': False,
            'needs_review': False,
            'issues': []
        }
        
        # Analyze file
        analysis = self.analyze_file(cbz_path)
        result['analysis'] = analysis
        result['needs_review'] = analysis['needs_review']
        result['issues'] = analysis['issues'].copy()
        
        if analysis['needs_review']:
            logger.warning(f"File needs manual review: {cbz_path.name}")
            return result
        
        # Update metadata if requested
        if update_metadata:
            metadata_success = self.update_metadata(
                cbz_path,
                analysis['series'],
                analysis['volume'],
                analysis['chapter'],
                preserve_existing
            )
            result['metadata_updated'] = metadata_success
            if not metadata_success:
                result['issues'].append("Metadata update failed")
        
        # Rename file
        rename_success, new_path, rename_issues = self.rename_file(cbz_path, dest_dir)
        result['renamed'] = rename_success
        result['new_path'] = new_path
        result['issues'].extend(rename_issues)
        
        # Overall success
        result['success'] = rename_success and (not update_metadata or result['metadata_updated'])
        
        return result
