from pathlib import Path
from typing import Optional, Tuple
import logging
from PIL import Image
import io

from cbz_utils import CBZFile
from database import Database

logger = logging.getLogger('manga-manager.cover')

class CoverManager:
    """Manages cover images for manga volumes."""
    
    def __init__(self, covers_cache_path: Path, database: Database):
        """
        Args:
            covers_cache_path: Path to cover cache directory (e.g., /data/covers)
            database: Database instance for querying existing covers
        """
        self.covers_path = Path(covers_cache_path)
        self.db = database
        
        # Ensure covers directory exists
        self.covers_path.mkdir(parents=True, exist_ok=True)
    
    def get_cover_path(self, series: str, volume: int) -> Path:
        """Get path where cover should be stored.
        
        Args:
            series: Series name
            volume: Volume number
        
        Returns:
            Path to cover file
        """
        series_dir = self.covers_path / series / f"Vol.{volume:03d}"
        series_dir.mkdir(parents=True, exist_ok=True)
        return series_dir / "cover.jpg"
    
    def has_cover(self, series: str, volume: int) -> bool:
        """Check if cover exists for a volume.
        
        Args:
            series: Series name
            volume: Volume number
        
        Returns:
            True if cover file exists
        """
        cover_path = self.get_cover_path(series, volume)
        return cover_path.exists()
    
    def extract_cover_from_cbz(self, cbz_path: Path, series: str, 
                               volume: int, force: bool = False) -> Tuple[bool, Optional[Path], str]:
        """Extract cover from CBZ file and save to cache.
        
        Args:
            cbz_path: Path to CBZ file
            series: Series name
            volume: Volume number
            force: If True, overwrite existing cover
        
        Returns:
            Tuple of (success, cover_path, message)
        """
        cover_path = self.get_cover_path(series, volume)
        
        # Check if cover already exists
        if cover_path.exists() and not force:
            logger.debug(f"Cover already exists for {series} Vol.{volume}")
            return True, cover_path, "Cover already exists"
        
        try:
            cbz = CBZFile(cbz_path)
            
            # Extract cover using CBZ utilities
            extracted = cbz.extract_cover(cover_path)
            
            if extracted:
                # Verify it's a valid image and convert to JPEG if needed
                self._ensure_jpeg(cover_path)
                logger.info(f"Extracted cover for {series} Vol.{volume} from {cbz_path.name}")
                return True, cover_path, "Cover extracted successfully"
            else:
                msg = f"No cover image found in {cbz_path.name}"
                logger.warning(msg)
                return False, None, msg
                
        except Exception as e:
            msg = f"Failed to extract cover from {cbz_path.name}: {e}"
            logger.error(msg)
            return False, None, msg
    
    def _ensure_jpeg(self, image_path: Path):
        """Ensure image is JPEG format, convert if necessary.
        
        Args:
            image_path: Path to image file
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if needed (remove alpha channel)
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                
                # Save as JPEG if not already
                if image_path.suffix.lower() != '.jpg':
                    new_path = image_path.with_suffix('.jpg')
                    img.save(new_path, 'JPEG', quality=95)
                    image_path.unlink()  # Remove original
                    logger.debug(f"Converted {image_path.name} to JPEG")
                elif img.format != 'JPEG':
                    img.save(image_path, 'JPEG', quality=95)
                    logger.debug(f"Re-saved {image_path.name} as JPEG")
                    
        except Exception as e:
            logger.warning(f"Could not ensure JPEG format for {image_path}: {e}")
    
    def get_existing_cover(self, series: str, volume: int) -> Optional[Path]:
        """Get existing cover from cache or database.
        
        Args:
            series: Series name
            volume: Volume number
        
        Returns:
            Path to cover file, or None if not found
        """
        # Check cache first
        cover_path = self.get_cover_path(series, volume)
        if cover_path.exists():
            return cover_path
        
        # Check database for cover path
        db_cover = self.db.get_volume_cover(series, volume)
        if db_cover and Path(db_cover).exists():
            return Path(db_cover)
        
        return None
    
    def copy_cover_to_cbz(self, cbz_path: Path, cover_source: Path) -> bool:
        """Add cover image to CBZ file.
        
        Args:
            cbz_path: Path to CBZ file
            cover_source: Path to cover image to add
        
        Returns:
            True if successful
        """
        try:
            # Read cover image
            with open(cover_source, 'rb') as f:
                cover_data = f.read()
            
            # Add to CBZ as 000_cover.jpg
            cbz = CBZFile(cbz_path)
            cbz.add_or_update_file('000_cover.jpg', cover_data)
            
            logger.info(f"Added cover to {cbz_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add cover to {cbz_path.name}: {e}")
            return False
    
    def remove_duplicate_cover(self, cbz_path: Path) -> bool:
        """Remove 000_cover.jpg from first chapter of volume.
        
        For first chapters, the first page (001.jpg) should be the cover,
        so 000_cover.jpg is redundant.
        
        Args:
            cbz_path: Path to CBZ file
        
        Returns:
            True if removed or didn't exist
        """
        try:
            cbz = CBZFile(cbz_path)
            
            if cbz.has_file('000_cover.jpg'):
                cbz.remove_file('000_cover.jpg')
                logger.info(f"Removed duplicate 000_cover.jpg from {cbz_path.name}")
                return True
            else:
                logger.debug(f"No 000_cover.jpg to remove from {cbz_path.name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to remove duplicate cover from {cbz_path.name}: {e}")
            return False
    
    def is_first_chapter_of_volume(self, chapter: float) -> bool:
        """Determine if chapter number indicates first chapter of volume.
        
        Args:
            chapter: Chapter number
        
        Returns:
            True if likely first chapter (e.g., 1, 1.0, 0)
        """
        # First chapter is typically 1 or 0 (some series start at 0)
        return chapter in (0, 0.0, 1, 1.0)
    
    def process_cover(self, cbz_path: Path, series: str, volume: Optional[int], 
                     chapter: float, is_new_volume: bool = False) -> dict:
        """Complete cover processing for a CBZ file.
        
        Logic:
        1. If first chapter of volume: Extract cover to cache, remove duplicate 000_cover.jpg
        2. If mid-volume chapter: Get cover from cache, add to CBZ as 000_cover.jpg
        3. If cover missing: Mark for manual review
        
        Args:
            cbz_path: Path to CBZ file
            series: Series name
            volume: Volume number (can be None)
            chapter: Chapter number
            is_new_volume: If True, this is known to be a new volume
        
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'cover_extracted': False,
            'cover_added': False,
            'duplicate_removed': False,
            'needs_review': False,
            'cover_path': None,
            'message': ''
        }
        
        # Can't process without volume number
        if volume is None:
            result['needs_review'] = True
            result['message'] = "Volume number required for cover processing"
            logger.warning(f"Cannot process cover for {cbz_path.name}: no volume number")
            return result
        
        is_first_chapter = self.is_first_chapter_of_volume(chapter)
        
        if is_first_chapter or is_new_volume:
            # This is (likely) the first chapter - extract cover
            success, cover_path, msg = self.extract_cover_from_cbz(cbz_path, series, volume)
            result['cover_extracted'] = success
            result['cover_path'] = cover_path
            result['message'] = msg
            
            if success:
                # Remove duplicate 000_cover.jpg from first chapter
                removed = self.remove_duplicate_cover(cbz_path)
                result['duplicate_removed'] = removed
                result['success'] = True
            else:
                # Could not extract cover - needs review
                result['needs_review'] = True
                result['message'] = f"Could not extract cover: {msg}"
        else:
            # Mid-volume chapter - add cover from cache
            existing_cover = self.get_existing_cover(series, volume)
            
            if existing_cover:
                added = self.copy_cover_to_cbz(cbz_path, existing_cover)
                result['cover_added'] = added
                result['cover_path'] = existing_cover
                result['success'] = added
                result['message'] = "Cover added from cache" if added else "Failed to add cover"
            else:
                # No cover available - needs review
                result['needs_review'] = True
                result['message'] = f"No cover found for {series} Vol.{volume}"
                logger.warning(f"No cover available for {series} Vol.{volume} - needs manual upload")
        
        return result
    
    def save_uploaded_cover(self, series: str, volume: int, cover_data: bytes) -> Tuple[bool, Optional[Path], str]:
        """Save manually uploaded cover.
        
        Args:
            series: Series name
            volume: Volume number
            cover_data: Cover image data
        
        Returns:
            Tuple of (success, cover_path, message)
        """
        try:
            cover_path = self.get_cover_path(series, volume)
            
            # Validate it's a valid image
            img = Image.open(io.BytesIO(cover_data))
            
            # Convert to RGB and save as JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
            
            img.save(cover_path, 'JPEG', quality=95)
            logger.info(f"Saved uploaded cover for {series} Vol.{volume}")
            
            return True, cover_path, "Cover uploaded successfully"
            
        except Exception as e:
            msg = f"Failed to save uploaded cover: {e}"
            logger.error(msg)
            return False, None, msg
