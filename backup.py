import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from nostr_sdk import (
    Client,
    PublicKey,
    Filter,
    RelayMessage,
    Kind,
    Timestamp,
    NostrSigner,
    Keys,
    RelayUrl
)

# Constants
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://relay.nostr.band",
    "wss://purplepag.es", # Good for profile info
]

async def main():
    parser = argparse.ArgumentParser(description="Backup Nostr events for a specific npub.")
    parser.add_argument("npub", help="The npub of the user to backup")
    parser.add_argument("--relays", nargs="+", help="Additional relays to query")
    parser.add_argument("--no-discovery", action="store_true", help="Skip smart relay discovery")
    parser.add_argument("--output", help="Custom output filename")
    
    args = parser.parse_args()

    # 1. Validation and Setup
    try:
        public_key = PublicKey.parse(args.npub)
        print(f"[*] Target Public Key (Hex): {public_key.to_hex()}")
    except Exception as e:
        print(f"[!] Invalid npub: {e}")
        sys.exit(1)

    # Setup Output Directory Structure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        backup_dir = Path(args.output)
    else:
        backup_dir = Path(f"backups/{args.npub}")

    # Create directory structure: backups/{npub}/posts/ and backups/{npub}/images/
    posts_dir = backup_dir / "posts"
    images_dir = backup_dir / "images"
    posts_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    output_path = posts_dir / f"backup_{timestamp}.jsonl"
    print(f"[*] Backup directory: {backup_dir}")
    print(f"[*] Saving events to: {output_path}")

    # 2. Initialize Client
    # We use a random signer because we are just reading
    keys = Keys.generate()
    signer = NostrSigner.keys(keys)
    client = Client(signer)
    
    # Add Default Relays
    for relay in DEFAULT_RELAYS:
        await client.add_relay(RelayUrl.parse(relay))
    
    if args.relays:
        for relay in args.relays:
            await client.add_relay(RelayUrl.parse(relay))

    await client.connect()
    print("[*] Connected to default relays.")

    # 3. Smart Discovery (Optional)
    if not args.no_discovery:
        print("[*] Discovering user's relay list (Kind 10002)...")
        # specific filter for discovery
        discovery_filter = Filter().author(public_key).kinds([Kind(10002), Kind(3)]).limit(1)
        
        # We use a short timeout for discovery
        events = await client.fetch_events(discovery_filter, timedelta(seconds=5)) # 5 seconds timeout

        new_relays = set()
        for event in events.to_vec():
            if event.kind().as_u16() == 10002:
                # Parse Kind 10002 tags
                for tag in event.tags().to_vec():
                    # Tags are complex in SDK, need to check structure
                    # tag.as_vec() returns list of strings
                    t = tag.as_vec()
                    if len(t) > 1 and t[0] == "r":
                        # t[1] is url, t[2] might be marker (read/write)
                        relay_url = t[1]
                        new_relays.add(relay_url)
            elif event.kind().as_u16() == 3:
                # Parse Kind 3 content if it has relay map
                try:
                    content = json.loads(event.content())
                    if isinstance(content, dict):
                        for url, perms in content.items():
                            if isinstance(perms, dict) and perms.get("write", True):
                                new_relays.add(url)
                except:
                    pass
        
        if new_relays:
            print(f"[*] Found {len(new_relays)} new relays from user metadata.")
            for relay in new_relays:
                await client.add_relay(RelayUrl.parse(relay))
            await client.connect()
            print("[*] Connected to discovered relays.")
        else:
            print("[*] No custom relays found or connection failed. Proceeding with defaults.")

    # 4. Main Subscription
    print("[*] Starting full backup (waiting for relays to complete)...")
    # Fetch events with a 60 second timeout for EOSE
    backup_filter = Filter().author(public_key)
    
    # fetch_events returns a collection of events (Events or list)
    try:
        events = await client.fetch_events(backup_filter, timedelta(seconds=60))
        print(f"[*] Received {events.len()} events.")

        seen_ids = set()
        stored_count = 0

        with open(output_path, "a") as f:
            for event in events.to_vec():
                event_id = event.id().to_hex()
                if event_id not in seen_ids:
                    seen_ids.add(event_id)
                    stored_count += 1
                    f.write(event.as_json() + "\n")
                    
        print(f"\n[+] Done! Saved {stored_count} events to {output_path}")

        # Download images
        print("\n[*] Downloading images...")
        from download_images import download_images_from_backup
        image_count = await download_images_from_backup(output_path, images_dir)
        print(f"[+] Downloaded {image_count} images to {images_dir}")

    except Exception as e:
        print(f"\n[!] Error during fetch: {e}")

if __name__ == "__main__":
    asyncio.run(main())
