# Manga Manager

Automated Docker-based manga processing system for organizing and maintaining a digital manga library.

## Features

- **Automated Processing Pipeline**: Watches download directory, processes CBZ files, and organizes into library
- **Metadata Management**: Standardizes ComicInfo.xml metadata for proper series/volume/chapter tracking
- **Cover Management**: Extracts, caches, and manages volume covers with intelligent detection
- **Manual Review UI**: Web interface for handling edge cases and manual interventions
- **Processing History**: SQLite database tracks all processed files with duplicate detection
- **Backup Support**: Optional backup copies of processed files
- **Kindle Conversion**: Optional conversion to Kindle format (when tool identified)

## Quick Start

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f manga-manager

# Access UI (once implemented)
# http://localhost:8080
```

## Documentation

- [Development Status & Changelog](.github/CHANGELOG.md)
- [Copilot Instructions](.github/copilot-instructions.md) - Architecture and conventions

## File Naming Convention

Processed manga follows standardized format:
```
{Series Name} Vol.{XXX} Ch.{XXXXX}.cbz
```

Examples:
- `Blue Period Vol.018 Ch.00076.cbz`
- `BECK Vol.001 Ch.00001.cbz`

## Directory Structure

```
/downloads   → New manga downloads (watched)
/processing  → Temporary processing workspace
/manga       → Final organized library
/kindle      → Kindle format output (optional)
/data        → Database and cover cache
```

**NAS Mapping:**
```
/mnt/rat-nas/
├── downloads/manga/           → /downloads
└── media/manga/
    ├── library/               → /manga
    ├── processing/            → /processing
    └── kindle/                → /kindle
```

## License

See LICENSE file for details.
