# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Nostr event backup tool that allows users to backup all events from a specified Nostr public key (npub) to a local JSONL file. The tool connects to multiple Nostr relays, optionally discovers user-specific relays, and fetches all events authored by the target public key.

## Setup and Dependencies

Install dependencies:
```bash
pip install -r requirements.txt
```

The project uses Python 3.14 and requires:
- `nostr-sdk>=0.0.5` - Python SDK for interacting with the Nostr protocol

## Running the Backup Tool

Basic usage:
```bash
python backup.py <npub>
```

This will create a directory structure under `backups/<npub>/`:
- `posts/` - Contains timestamped JSONL files with all events
- `images/` - Contains all downloaded images from the events
- `images/url_mapping.json` - Maps original URLs to downloaded filenames

With options:
```bash
# Skip relay discovery (faster but may miss events)
python backup.py <npub> --no-discovery

# Add custom relays
python backup.py <npub> --relays wss://relay.example.com wss://another-relay.com

# Specify custom output directory
python backup.py <npub> --output custom_backup_dir
```

## Standalone Image Download

You can also download images from an existing backup file independently:
```bash
python download_images.py <backup_file.jsonl> --output <images_directory>
```

## Architecture

### Main Components

**backup.py**
- Main entry point for the backup tool
- Implements async event fetching from Nostr relays
- Four-phase operation:
  1. Validation & Setup - Parses npub, creates directory structure (`backups/{npub}/posts/` and `backups/{npub}/images/`)
  2. Client Initialization - Connects to default and custom relays
  3. Smart Relay Discovery - Optional phase that queries for Kind 10002 (relay list) and Kind 3 (contact list) to discover user-specific relays
  4. Event Fetching & Image Download - Fetches all events with 60s timeout, then automatically downloads all images

**download_images.py**
- Extracts image URLs from event content and tags
- Downloads images concurrently with configurable parallelism
- Supports multiple image hosts (nostr.build, void.cat, imgur, etc.)
- Creates a url_mapping.json file to map original URLs to local filenames
- Can be used standalone or imported by backup.py

**inspect_*.py files**
- Small utility scripts used during development to inspect the nostr-sdk API
- Not part of the main backup functionality

### Key Design Patterns

**Relay Management**
- Default relay list includes major Nostr relays (backup.py:19-25)
- Smart discovery feature queries Kind 10002 (relay lists) and Kind 3 (contact lists) to find user-specific relays
- All relay connections are managed through the nostr-sdk Client

**Event Storage**
- Events are stored as JSONL (JSON Lines format) with one event per line
- Deduplication is handled via event ID tracking
- Directory structure: `backups/{npub}/posts/backup_{timestamp}.jsonl`
- Images are stored in: `backups/{npub}/images/`
- Each backup run creates a new timestamped JSONL file but reuses the same images directory (skipping already downloaded images)

**Async Operations**
- All Nostr operations are async using asyncio
- The Client.fetch_events() method includes configurable timeouts to handle slow relays
- Discovery phase uses a 5-second timeout, main fetch uses 60 seconds

### Important Implementation Details

**Signer Requirement**
- The nostr-sdk Client requires a signer even for read-only operations
- A random key pair is generated for this purpose (backup.py:56-58)
- This is not used for any signing operations, only to satisfy the SDK's API requirements

**Event Filtering**
- Uses Filter.author() to fetch only events from the target public key
- Discovery phase filters for specific kinds (10002, 3) with limit(1)
- Main backup fetches all event kinds without additional filtering

**Timeout Strategy**
- Discovery: 5 seconds - quick check for relay metadata
- Main fetch: 60 seconds - ensures enough time for relays to respond with full event history
- Image downloads: 30 seconds per image with 10 concurrent downloads by default
- Adjust these timeouts if needed for different network conditions

**Image Extraction**
- Images are extracted from markdown syntax in content: `![alt](url)`
- Images are extracted from event tags: `["image", "url"]`, `["picture", "url"]`, etc.
- URLs from known image hosting services are automatically detected
- Supports common formats: JPG, PNG, GIF, WebP, SVG, BMP
