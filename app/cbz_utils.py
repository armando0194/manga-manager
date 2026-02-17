import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger('manga-manager.cbz')

class CBZFile:
    """Utilities for reading and writing CBZ (Comic Book ZIP) files."""
    
    def __init__(self, file_path):
        """
        Args:
            file_path: Path to CBZ file
        """
        self.file_path = Path(file_path)
        self._validate_cbz()
    
    def _validate_cbz(self):
        """Validate that file is a valid ZIP archive."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"CBZ file not found: {self.file_path}")
        
        if not zipfile.is_zipfile(self.file_path):
            raise ValueError(f"File is not a valid ZIP/CBZ archive: {self.file_path}")
    
    def list_files(self) -> List[str]:
        """List all files in the CBZ archive.
        
        Returns:
            List of file paths inside the archive
        """
        with zipfile.ZipFile(self.file_path, 'r') as zf:
            return zf.namelist()
    
    def get_image_files(self) -> List[str]:
        """Get list of image files in the archive.
        
        Returns:
            List of image file paths, sorted naturally
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        files = self.list_files()
        
        # Filter image files
        images = [
            f for f in files 
            if Path(f).suffix.lower() in image_extensions
            and not f.startswith('__MACOSX')  # Skip Mac OS metadata
            and not Path(f).name.startswith('.')  # Skip hidden files
        ]
        
        # Sort naturally (001.jpg, 002.jpg, etc.)
        return sorted(images, key=self._natural_sort_key)
    
    def _natural_sort_key(self, text):
        """Natural sort key for filenames with numbers."""
        import re
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(text))]
    
    def has_file(self, filename: str) -> bool:
        """Check if specific file exists in archive.
        
        Args:
            filename: File to check for (e.g., 'ComicInfo.xml')
        
        Returns:
            True if file exists
        """
        return filename in self.list_files()
    
    def read_file(self, filename: str) -> bytes:
        """Read file content from archive.
        
        Args:
            filename: File to read
        
        Returns:
            File content as bytes
        """
        with zipfile.ZipFile(self.file_path, 'r') as zf:
            return zf.read(filename)
    
    def extract_file(self, filename: str, dest_path: Path) -> Path:
        """Extract specific file from archive.
        
        Args:
            filename: File to extract
            dest_path: Destination path (file or directory)
        
        Returns:
            Path to extracted file
        """
        dest_path = Path(dest_path)
        
        with zipfile.ZipFile(self.file_path, 'r') as zf:
            if dest_path.is_dir():
                # Extract to directory with original filename
                extracted = zf.extract(filename, dest_path)
                return Path(extracted)
            else:
                # Extract to specific file path
                content = zf.read(filename)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(content)
                return dest_path
    
    def get_cover_image(self) -> Optional[str]:
        """Get cover image filename from archive.
        
        Priority:
        1. 000_cover.jpg (dedicated cover)
        2. First image file (sorted)
        
        Returns:
            Filename of cover image, or None if no images
        """
        images = self.get_image_files()
        
        if not images:
            return None
        
        # Check for dedicated cover file
        for img in images:
            if Path(img).name.lower() in ['000_cover.jpg', '000_cover.png', '000.jpg', '000.png']:
                return img
        
        # Return first image
        return images[0]
    
    def extract_cover(self, dest_path: Path) -> Optional[Path]:
        """Extract cover image from archive.
        
        Args:
            dest_path: Destination file path for cover
        
        Returns:
            Path to extracted cover, or None if no cover found
        """
        cover = self.get_cover_image()
        
        if not cover:
            logger.warning(f"No cover image found in {self.file_path.name}")
            return None
        
        return self.extract_file(cover, dest_path)
    
    def add_or_update_file(self, filename: str, content: bytes, output_path: Optional[Path] = None):
        """Add or update a file in the CBZ archive.
        
        Args:
            filename: File to add/update (e.g., 'ComicInfo.xml', '000_cover.jpg')
            content: File content as bytes
            output_path: Path for modified CBZ (if None, overwrites original)
        """
        output_path = output_path or self.file_path
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            temp_cbz = temp_dir / 'temp.cbz'
            
            # Copy all files except the one we're updating
            with zipfile.ZipFile(self.file_path, 'r') as zf_in:
                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_DEFLATED) as zf_out:
                    for item in zf_in.namelist():
                        if item != filename:
                            data = zf_in.read(item)
                            zf_out.writestr(item, data)
                    
                    # Add new/updated file
                    zf_out.writestr(filename, content)
            
            # Replace original or write to new location
            shutil.move(str(temp_cbz), str(output_path))
        
        logger.info(f"Updated {filename} in {output_path.name}")
    
    def remove_file(self, filename: str, output_path: Optional[Path] = None):
        """Remove a file from the CBZ archive.
        
        Args:
            filename: File to remove
            output_path: Path for modified CBZ (if None, overwrites original)
        """
        if not self.has_file(filename):
            logger.debug(f"{filename} not found in {self.file_path.name}")
            return
        
        output_path = output_path or self.file_path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            temp_cbz = temp_dir / 'temp.cbz'
            
            # Copy all files except the one we're removing
            with zipfile.ZipFile(self.file_path, 'r') as zf_in:
                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_DEFLATED) as zf_out:
                    for item in zf_in.namelist():
                        if item != filename:
                            data = zf_in.read(item)
                            zf_out.writestr(item, data)
            
            shutil.move(str(temp_cbz), str(output_path))
        
        logger.info(f"Removed {filename} from {output_path.name}")
