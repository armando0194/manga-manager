# Testing Manga Manager

## Quick Test Setup

### 1. Create Test Directories

```bash
# Create local test directories (don't need actual NAS mounts for testing)
mkdir -p test-data/{downloads,processing,manga,kindle,data}
```

### 2. Update docker-compose.yml for Testing

Create `docker-compose.test.yml`:

```yaml
version: '3.8'

services:
  manga-manager:
    build: .
    container_name: manga-manager-test
    volumes:
      - ./app:/app
      - ./config:/config
      - ./logs:/logs
      - ./data:/data
      - ./test-data/downloads:/downloads
      - ./test-data/processing:/processing
      - ./test-data/manga:/manga
      - ./test-data/kindle:/kindle
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=DEBUG
    stdin_open: true
    tty: true
    command: /bin/bash  # Keep container running for testing
```

### 3. Test Individual Components

#### Option A: Run Test Script

```bash
# Start the container
docker compose -f docker-compose.test.yml up -d

# Copy a test CBZ file to downloads
cp /path/to/your/test.cbz test-data/downloads/

# Run the test script
docker compose -f docker-compose.test.yml exec manga-manager \
  python test_processing.py /downloads/test.cbz

# View logs
docker compose -f docker-compose.test.yml logs
```

#### Option B: Interactive Testing

```bash
# Enter the container
docker compose -f docker-compose.test.yml exec manga-manager /bin/bash

# Inside container - test individual components
python3 << 'EOF'
from cbz_utils import CBZFile
from pathlib import Path

# Test CBZ reading
cbz = CBZFile('/downloads/test.cbz')
print(f"Files: {len(cbz.list_files())}")
print(f"Images: {len(cbz.get_image_files())}")
print(f"Cover: {cbz.get_cover_image()}")
EOF
```

### 4. Test Filename Parsing

```bash
docker compose -f docker-compose.test.yml exec manga-manager python3 << 'EOF'
from filename_parser import FilenameParser

parser = FilenameParser()

# Test various filename formats
test_files = [
    "Blue Period Vol.018 Ch.00076.cbz",
    "BECK v01 c001.cbz",
    "One Piece - Chapter 1050.cbz",
    "[Group] Series Name - Ch. 76.5.cbz"
]

for filename in test_files:
    result = parser.parse(filename)
    print(f"{filename}")
    print(f"  → {result}")
    print()
EOF
```

### 5. Test Full Processing Pipeline

```bash
# Run container in foreground to see logs
docker compose -f docker-compose.test.yml up

# In another terminal, drop a CBZ file
cp test-file.cbz test-data/downloads/

# Watch the logs for processing
```

## What to Test

### Basic Tests
1. ✅ File detection (copy CBZ to downloads, check logs)
2. ✅ Duplicate detection (copy same file twice)
3. ✅ Filename parsing (various formats)
4. ✅ Metadata reading (files with/without ComicInfo.xml)
5. ✅ Cover extraction

### Without Full Pipeline
Since we haven't wired everything together yet, use the test script to verify:
- CBZ files can be opened and read
- Filenames are parsed correctly
- Metadata is extracted
- Covers can be extracted
- Files would be renamed correctly (dry run)

## Expected Output

When you run the test script, you should see:
```
📁 Testing: Blue Period Vol.018 Ch.00076.cbz

1️⃣  CBZ File Analysis
------------------------------------------------------------
   Total files: 45
   Image files: 44
   Cover image: 001.jpg
   Has ComicInfo.xml: Yes
   ✅ CBZ utilities working

2️⃣  Metadata Analysis
------------------------------------------------------------
   Series: Blue Period
   Volume: 18
   Chapter: 76
   Title: Chapter 76
   ✅ Metadata handler working

... and so on
```

## Cleanup

```bash
# Stop container
docker compose -f docker-compose.test.yml down

# Remove test data
rm -rf test-data/
```

## Next Steps

After testing components individually, we need to:
1. Wire everything together in the main processor
2. Implement the full processing pipeline
3. Add error handling and recovery
4. Build the web UI for manual review
