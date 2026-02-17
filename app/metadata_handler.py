from lxml import etree
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger('manga-manager.metadata')

class ComicInfo:
    """Handler for ComicInfo.xml metadata in CBZ files."""
    
    # ComicInfo.xml schema namespace (optional, but good practice)
    NAMESPACE = None  # ComicInfo typically doesn't use namespaces
    
    def __init__(self, xml_content: Optional[bytes] = None):
        """
        Args:
            xml_content: Existing ComicInfo.xml content, or None to create new
        """
        if xml_content:
            self.root = etree.fromstring(xml_content)
        else:
            self.root = etree.Element('ComicInfo')
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'ComicInfo':
        """Load ComicInfo from XML file.
        
        Args:
            file_path: Path to ComicInfo.xml file
        
        Returns:
            ComicInfo instance
        """
        with open(file_path, 'rb') as f:
            return cls(f.read())
    
    def get_field(self, field_name: str, default: Any = None) -> Any:
        """Get value of a metadata field.
        
        Args:
            field_name: Field name (e.g., 'Series', 'Number', 'Volume')
            default: Default value if field doesn't exist
        
        Returns:
            Field value or default
        """
        element = self.root.find(field_name)
        return element.text if element is not None else default
    
    def set_field(self, field_name: str, value: Any):
        """Set value of a metadata field.
        
        Args:
            field_name: Field name (e.g., 'Series', 'Number', 'Volume')
            value: Value to set (converted to string)
        """
        element = self.root.find(field_name)
        
        if element is None:
            # Create new element
            element = etree.SubElement(self.root, field_name)
        
        element.text = str(value) if value is not None else ''
    
    def remove_field(self, field_name: str):
        """Remove a metadata field.
        
        Args:
            field_name: Field name to remove
        """
        element = self.root.find(field_name)
        if element is not None:
            self.root.remove(element)
    
    @property
    def series(self) -> Optional[str]:
        """Get series name."""
        return self.get_field('Series')
    
    @series.setter
    def series(self, value: str):
        """Set series name."""
        self.set_field('Series', value)
    
    @property
    def volume(self) -> Optional[int]:
        """Get volume number."""
        vol = self.get_field('Volume')
        return int(vol) if vol else None
    
    @volume.setter
    def volume(self, value: int):
        """Set volume number."""
        self.set_field('Volume', value)
    
    @property
    def number(self) -> Optional[float]:
        """Get chapter/issue number."""
        num = self.get_field('Number')
        return float(num) if num else None
    
    @number.setter
    def number(self, value: float):
        """Set chapter/issue number."""
        self.set_field('Number', value)
    
    @property
    def title(self) -> Optional[str]:
        """Get chapter title."""
        return self.get_field('Title')
    
    @title.setter
    def title(self, value: str):
        """Set chapter title."""
        self.set_field('Title', value)
    
    @property
    def summary(self) -> Optional[str]:
        """Get summary/description."""
        return self.get_field('Summary')
    
    @summary.setter
    def summary(self, value: str):
        """Set summary/description."""
        self.set_field('Summary', value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary.
        
        Returns:
            Dictionary of all metadata fields
        """
        return {elem.tag: elem.text for elem in self.root}
    
    def to_xml(self, pretty_print: bool = True) -> bytes:
        """Convert to XML bytes.
        
        Args:
            pretty_print: Format XML with indentation
        
        Returns:
            XML content as bytes
        """
        return etree.tostring(
            self.root,
            xml_declaration=True,
            encoding='utf-8',
            pretty_print=pretty_print
        )
    
    def validate_required_fields(self, required: list) -> bool:
        """Check if required fields are present and non-empty.
        
        Args:
            required: List of required field names
        
        Returns:
            True if all required fields present
        """
        for field in required:
            value = self.get_field(field)
            if not value:
                logger.warning(f"Required field '{field}' is missing or empty")
                return False
        return True
    
    def __repr__(self):
        return f"ComicInfo(series={self.series}, volume={self.volume}, number={self.number})"
