import re
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger('manga-manager.parser')

class FilenameParser:
    """Parse manga filenames to extract series, volume, and chapter information."""
    
    # Common patterns for manga filenames
    PATTERNS = [
        # Pattern: "Series Name Vol.018 Ch.00076.cbz"
        r'^(?P<series>.+?)\s+Vol\.(?P<volume>\d+)\s+Ch\.(?P<chapter>[\d.]+)',
        
        # Pattern: "Series Name v18 c76.cbz"
        r'^(?P<series>.+?)\s+v(?P<volume>\d+)\s+c(?P<chapter>[\d.]+)',
        
        # Pattern: "Series Name - Volume 18 - Chapter 76.cbz"
        r'^(?P<series>.+?)\s*-\s*Volume\s+(?P<volume>\d+)\s*-\s*Chapter\s+(?P<chapter>[\d.]+)',
        
        # Pattern: "[Group] Series Name - Ch. 76.cbz" (no volume)
        r'^(?:\[.+?\]\s*)?(?P<series>.+?)\s*-\s*Ch\.?\s*(?P<chapter>[\d.]+)',
        
        # Pattern: "Series Name Chapter 76.cbz" (no volume)
        r'^(?P<series>.+?)\s+Chapter\s+(?P<chapter>[\d.]+)',
        
        # Pattern: "Series Name 076.cbz" (just chapter number)
        r'^(?P<series>.+?)\s+(?P<chapter>\d{3,})',
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.PATTERNS]
    
    def parse(self, filename: str) -> Dict[str, Any]:
        """Parse filename to extract metadata.
        
        Args:
            filename: Filename to parse (with or without .cbz extension)
        
        Returns:
            Dictionary with keys: series, volume, chapter, original_filename
        """
        # Remove .cbz extension
        name = Path(filename).stem
        
        result = {
            'series': None,
            'volume': None,
            'chapter': None,
            'original_filename': filename
        }
        
        # Try each pattern
        for pattern in self.compiled_patterns:
            match = pattern.match(name)
            if match:
                groups = match.groupdict()
                
                # Extract series name and clean it
                if 'series' in groups:
                    result['series'] = self._clean_series_name(groups['series'])
                
                # Extract volume number
                if 'volume' in groups and groups['volume']:
                    result['volume'] = int(groups['volume'])
                
                # Extract chapter number (can be decimal like 76.5)
                if 'chapter' in groups and groups['chapter']:
                    chapter = groups['chapter']
                    result['chapter'] = float(chapter) if '.' in chapter else int(chapter)
                
                logger.debug(f"Parsed '{filename}' -> {result}")
                return result
        
        # No pattern matched
        logger.warning(f"Could not parse filename: {filename}")
        return result
    
    def _clean_series_name(self, series: str) -> str:
        """Clean up series name.
        
        Args:
            series: Raw series name from filename
        
        Returns:
            Cleaned series name
        """
        # Remove leading/trailing whitespace
        series = series.strip()
        
        # Remove common prefixes like [Group Name]
        series = re.sub(r'^\[.+?\]\s*', '', series)
        
        # Remove trailing dashes/underscores
        series = series.rstrip(' -_')
        
        return series
    
    def standardize_filename(self, series: str, volume: Optional[int], chapter: float, 
                            volume_digits: int = 3, chapter_digits: int = 5) -> str:
        """Generate standardized filename.
        
        Args:
            series: Series name
            volume: Volume number (can be None)
            chapter: Chapter number (can be decimal)
            volume_digits: Number of digits for volume padding
            chapter_digits: Number of digits for chapter padding
        
        Returns:
            Standardized filename without extension
        """
        # Format volume with padding
        vol_str = f"Vol.{volume:0{volume_digits}d}" if volume else "Vol.???"
        
        # Format chapter with padding (handle decimals like 76.5)
        if isinstance(chapter, float) and chapter % 1 != 0:
            # Decimal chapter (e.g., 76.5)
            whole = int(chapter)
            decimal = str(chapter).split('.')[1]
            ch_str = f"Ch.{whole:0{chapter_digits}d}.{decimal}"
        else:
            # Integer chapter
            ch_str = f"Ch.{int(chapter):0{chapter_digits}d}"
        
        return f"{series} {vol_str} {ch_str}"


class SeriesDetector:
    """Detect and match series names against existing library."""
    
    def __init__(self, manga_library_path: Path):
        """
        Args:
            manga_library_path: Path to manga library directory
        """
        self.library_path = Path(manga_library_path)
        self._series_cache = None
    
    def get_existing_series(self) -> list:
        """Get list of existing series in library.
        
        Returns:
            List of series names (directory names)
        """
        if self._series_cache is None:
            if self.library_path.exists():
                self._series_cache = [
                    d.name for d in self.library_path.iterdir() 
                    if d.is_dir() and not d.name.startswith('.')
                ]
            else:
                self._series_cache = []
        
        return self._series_cache
    
    def find_series_match(self, series_name: str) -> Optional[str]:
        """Find matching series in library.
        
        Uses exact match first, then fuzzy matching.
        
        Args:
            series_name: Series name to match
        
        Returns:
            Matched series name from library, or None if no match
        """
        existing = self.get_existing_series()
        
        # Exact match (case-insensitive)
        for existing_series in existing:
            if existing_series.lower() == series_name.lower():
                return existing_series
        
        # Fuzzy match (simple substring matching)
        series_lower = series_name.lower()
        for existing_series in existing:
            existing_lower = existing_series.lower()
            
            # Check if one is substring of the other
            if series_lower in existing_lower or existing_lower in series_lower:
                logger.info(f"Fuzzy matched '{series_name}' to '{existing_series}'")
                return existing_series
        
        # No match found
        logger.info(f"No existing series match for '{series_name}'")
        return None
    
    def normalize_series_name(self, series_name: str) -> str:
        """Normalize series name for consistency.
        
        Args:
            series_name: Raw series name
        
        Returns:
            Normalized series name
        """
        # Try to match existing series first
        match = self.find_series_match(series_name)
        if match:
            return match
        
        # Otherwise, return cleaned version
        # Title case, remove extra spaces
        return ' '.join(series_name.split())
