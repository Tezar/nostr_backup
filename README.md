# Nostr Backup Tool

A comprehensive backup tool for Nostr profiles that archives all events and images to local storage. Built with [Claude Code](https://claude.ai/code).

## Features

- 📥 **Complete Event Backup** - Downloads all events (notes, reactions, profile info, etc.) from a Nostr public key
- 🖼️ **Automatic Image Download** - Extracts and downloads all images referenced in events
- 🔍 **Smart Relay Discovery** - Automatically discovers and queries user-specific relays
- 📁 **Organized Storage** - Clean directory structure organized by npub
- ⚡ **Async & Concurrent** - Fast downloads with configurable parallelism
- 🔄 **Deduplication** - Skips already downloaded images on subsequent runs
- 📋 **URL Mapping** - Maintains mapping between original URLs and downloaded files

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup

1. Clone this repository:
```bash
git clone <repository-url>
cd nostr_backup
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Backup

Back up all events and images for a Nostr public key:

```bash
python backup.py npub1yourpublickey...
```

This creates a directory structure:
```
backups/
└── npub1yourpublickey.../
    ├── posts/
    │   └── backup_20260113_123456.jsonl
    └── images/
        ├── image1.jpg
        ├── image2.png
        ├── ...
        └── url_mapping.json
```

### Advanced Options

**Skip relay discovery** (faster, but may miss events):
```bash
python backup.py npub1... --no-discovery
```

**Add custom relays**:
```bash
python backup.py npub1... --relays wss://relay.example.com wss://another-relay.com
```

**Specify custom output directory**:
```bash
python backup.py npub1... --output /path/to/custom/directory
```

### Standalone Image Download

Download images from an existing backup file:

```bash
python download_images.py backup_file.jsonl --output images_directory
```

Options:
- `--concurrency N` - Number of concurrent downloads (default: 10)

## Output Format

### Events (JSONL)

Events are stored in JSON Lines format (`.jsonl`), with one complete event per line:

```json
{"id":"abc123...","pubkey":"def456...","created_at":1234567890,"kind":1,"tags":[],"content":"Hello Nostr!","sig":"..."}
```

This format is:
- Easy to parse line-by-line
- Append-friendly for incremental backups
- Compatible with standard JSON tools

### Images

Images are downloaded with content-based filenames and organized in the `images/` directory. The `url_mapping.json` file maintains the relationship between original URLs and local filenames:

```json
{
  "https://nostr.build/i/abc123.jpg": "abc123def456.jpg",
  "https://void.cat/d/xyz789.png": "xyz789abc012.png"
}
```

## Supported Image Sources

The tool automatically detects and downloads images from:
- nostr.build
- void.cat
- imgur.com
- primal.net
- Any URL with common image extensions (.jpg, .png, .gif, .webp, .svg, .bmp)

Images are extracted from:
- Markdown syntax: `![alt](url)`
- Event tags: `["image", "url"]`, `["picture", "url"]`, `["avatar", "url"]`, etc.
- Plain URLs in content

## Architecture

### Backup Process

1. **Validation & Setup** - Parse npub and create directory structure
2. **Client Initialization** - Connect to default and custom relays
3. **Smart Relay Discovery** (optional) - Query Kind 10002 and Kind 3 events for user-specific relays
4. **Event Fetching** - Download all events with configurable timeout
5. **Image Download** - Extract and download all images concurrently

### Default Relays

The tool connects to these popular Nostr relays by default:
- wss://relay.damus.io
- wss://nos.lol
- wss://relay.primal.net
- wss://relay.nostr.band
- wss://purplepag.es

### Timeouts

- **Relay Discovery**: 5 seconds
- **Event Fetching**: 60 seconds
- **Image Downloads**: 30 seconds per image

## Troubleshooting

### No events found

- Verify the npub is correct
- Try adding custom relays with `--relays`
- Check if the user has posted to the default relays

### Missing images

- Some images may be hosted on services that are down or rate-limited
- Failed downloads are logged with `[✗]` prefix
- Re-run the backup to retry failed downloads

### Connection issues

- Ensure you have a stable internet connection
- Some relays may be temporarily unavailable
- Add more relays with `--relays` to increase coverage

## Development

This project was built using [Claude Code](https://claude.ai/code), an AI-powered development tool.

### Project Structure

```
nostr_backup/
├── backup.py              # Main backup script
├── download_images.py     # Image download utilities
├── inspect_*.py          # API inspection utilities
├── requirements.txt      # Python dependencies
├── CLAUDE.md            # Claude Code guidance
└── README.md            # This file
```

### Dependencies

- `nostr-sdk` - Python SDK for Nostr protocol
- `aiohttp` - Async HTTP client for image downloads

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - feel free to use this project for any purpose.

## Acknowledgments

- Built with [Claude Code](https://claude.ai/code)
- Uses [nostr-sdk](https://github.com/rust-nostr/nostr) for Nostr protocol implementation
- Inspired by the need for data sovereignty in decentralized social networks

## Support

For issues or questions:
1. Check existing GitHub issues
2. Create a new issue with detailed information
3. Include error messages and steps to reproduce

---

**Note**: This tool is for personal backup purposes. Always respect content ownership and privacy when backing up and storing data.
