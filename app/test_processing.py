#!/usr/bin/env python3
"""
Test script for manga-manager components

Usage:
    python test_processing.py /path/to/test.cbz
"""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cbz_utils import CBZFile
from metadata_handler import ComicInfo
from filename_parser import FilenameParser, SeriesDetector
from file_renamer import FileRenamer
from cover_manager import CoverManager
from database import Database
from utils import setup_logging

def test_cbz_file(cbz_path: str):
    """Test processing a single CBZ file."""
    
    # Setup logging
    logger = setup_logging('DEBUG', '/logs/test.log')
    logger.info("=" * 80)
    logger.info(f"Testing CBZ file: {cbz_path}")
    logger.info("=" * 80)
    
    cbz_path = Path(cbz_path)
    
    if not cbz_path.exists():
        print(f"❌ File not found: {cbz_path}")
        return
    
    print(f"\n📁 Testing: {cbz_path.name}\n")
    
    # Test 1: CBZ Utilities
    print("1️⃣  CBZ File Analysis")
    print("-" * 60)
    try:
        cbz = CBZFile(cbz_path)
        files = cbz.list_files()
        images = cbz.get_image_files()
        cover = cbz.get_cover_image()
        has_metadata = cbz.has_file('ComicInfo.xml')
        
        print(f"   Total files: {len(files)}")
        print(f"   Image files: {len(images)}")
        print(f"   Cover image: {cover or 'Not found'}")
        print(f"   Has ComicInfo.xml: {'Yes' if has_metadata else 'No'}")
        print("   ✅ CBZ utilities working\n")
    except Exception as e:
        print(f"   ❌ CBZ utilities failed: {e}\n")
        return
    
    # Test 2: Metadata Handler
    print("2️⃣  Metadata Analysis")
    print("-" * 60)
    try:
        if has_metadata:
            xml_content = cbz.read_file('ComicInfo.xml')
            comic_info = ComicInfo(xml_content)
            print(f"   Series: {comic_info.series or 'Not set'}")
            print(f"   Volume: {comic_info.volume or 'Not set'}")
            print(f"   Chapter: {comic_info.number or 'Not set'}")
            print(f"   Title: {comic_info.title or 'Not set'}")
        else:
            print("   No ComicInfo.xml found")
        print("   ✅ Metadata handler working\n")
    except Exception as e:
        print(f"   ⚠️  Metadata parsing failed: {e}\n")
    
    # Test 3: Filename Parser
    print("3️⃣  Filename Parsing")
    print("-" * 60)
    try:
        parser = FilenameParser()
        parsed = parser.parse(cbz_path.name)
        print(f"   Series: {parsed['series'] or 'Not detected'}")
        print(f"   Volume: {parsed['volume'] or 'Not detected'}")
        print(f"   Chapter: {parsed['chapter'] or 'Not detected'}")
        
        if all([parsed['series'], parsed['volume'], parsed['chapter']]):
            standardized = parser.standardize_filename(
                parsed['series'], parsed['volume'], parsed['chapter']
            )
            print(f"   Standardized: {standardized}.cbz")
        print("   ✅ Filename parser working\n")
    except Exception as e:
        print(f"   ❌ Filename parser failed: {e}\n")
    
    # Test 4: File Renamer (Analysis Only)
    print("4️⃣  File Renamer Analysis")
    print("-" * 60)
    try:
        db = Database('/tmp/test_manga.db')
        renamer = FileRenamer('/manga', volume_digits=3, chapter_digits=5)
        analysis = renamer.analyze_file(cbz_path)
        
        print(f"   Detected series: {analysis['series'] or 'Unknown'}")
        print(f"   Detected volume: {analysis['volume'] or 'Unknown'}")
        print(f"   Detected chapter: {analysis['chapter'] or 'Unknown'}")
        print(f"   Needs review: {'Yes' if analysis['needs_review'] else 'No'}")
        
        if analysis['issues']:
            print(f"   Issues: {', '.join(analysis['issues'])}")
        
        if not analysis['needs_review']:
            new_name = renamer.generate_standard_filename(
                analysis['series'], analysis['volume'], analysis['chapter']
            )
            print(f"   New filename: {new_name}")
        
        print("   ✅ File renamer working\n")
        db.close()
    except Exception as e:
        print(f"   ❌ File renamer failed: {e}\n")
    
    # Test 5: Cover Manager
    print("5️⃣  Cover Management")
    print("-" * 60)
    try:
        db = Database('/tmp/test_manga.db')
        cover_mgr = CoverManager('/tmp/test_covers', db)
        
        # Try to extract cover
        if analysis['series'] and analysis['volume']:
            success, cover_path, msg = cover_mgr.extract_cover_from_cbz(
                cbz_path, analysis['series'], analysis['volume'], force=True
            )
            print(f"   Cover extraction: {'Success' if success else 'Failed'}")
            print(f"   Message: {msg}")
            if cover_path:
                print(f"   Cover saved to: {cover_path}")
        else:
            print("   ⚠️  Cannot extract cover: series/volume not detected")
        
        print("   ✅ Cover manager working\n")
        db.close()
    except Exception as e:
        print(f"   ❌ Cover manager failed: {e}\n")
    
    print("=" * 60)
    print("✅ All component tests completed!")
    print("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_processing.py /path/to/test.cbz")
        print("\nExample:")
        print("  docker compose exec manga-manager python test_processing.py /downloads/test.cbz")
        sys.exit(1)
    
    test_cbz_file(sys.argv[1])
