import asyncio
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import aiohttp
from datetime import datetime

# Common image hosting domains and extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico'}
IMAGE_HOSTS = {'nostr.build', 'void.cat', 'imgur.com', 'i.imgur.com', 'primal.net', 'image.nostr.build'}

def extract_urls_from_content(content):
    """Extract URLs from markdown and plain text content."""
    urls = set()

    # Markdown images: ![alt](url)
    markdown_pattern = r'!\[.*?\]\((https?://[^\s)]+)\)'
    urls.update(re.findall(markdown_pattern, content))

    # Plain URLs that look like images
    url_pattern = r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|gif|webp|bmp|svg)'
    urls.update(re.findall(url_pattern, content, re.IGNORECASE))

    # Any URL from known image hosts
    host_pattern = r'https?://(?:' + '|'.join(re.escape(h) for h in IMAGE_HOSTS) + r')[^\s<>"()]+'
    urls.update(re.findall(host_pattern, content))

    return urls

def extract_urls_from_tags(tags):
    """Extract image URLs from event tags."""
    urls = set()

    for tag in tags:
        if len(tag) < 2:
            continue

        tag_name = tag[0]
        tag_value = tag[1]

        # Common image tags
        if tag_name in ['image', 'url', 'thumb', 'banner', 'picture', 'avatar']:
            if tag_value.startswith('http'):
                urls.add(tag_value)

        # Check if any tag value looks like an image URL
        elif tag_value.startswith('http'):
            parsed = urlparse(tag_value)
            if any(parsed.path.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                urls.add(tag_value)
            elif any(host in parsed.netloc for host in IMAGE_HOSTS):
                urls.add(tag_value)

    return urls

def sanitize_filename(url):
    """Create a safe filename from URL."""
    parsed = urlparse(url)
    filename = parsed.path.split('/')[-1]

    # If no filename or extension, use hash of URL
    if not filename or '.' not in filename:
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        # Try to get extension from content-type later
        filename = f"{url_hash}.jpg"

    # Remove any unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    return filename

async def download_image(session, url, output_dir, semaphore):
    """Download a single image with retry logic."""
    async with semaphore:
        filename = sanitize_filename(url)
        output_path = output_dir / filename

        # Skip if already downloaded
        if output_path.exists():
            print(f"[SKIP] {filename} (already exists)")
            return True

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    content = await response.read()

                    # Try to get better extension from content-type
                    content_type = response.headers.get('content-type', '')
                    if 'image/' in content_type:
                        ext_map = {
                            'image/jpeg': '.jpg',
                            'image/png': '.png',
                            'image/gif': '.gif',
                            'image/webp': '.webp',
                            'image/svg+xml': '.svg'
                        }
                        if content_type in ext_map and not any(filename.endswith(ext) for ext in IMAGE_EXTENSIONS):
                            filename = filename.rsplit('.', 1)[0] + ext_map[content_type]
                            output_path = output_dir / filename

                    output_path.write_bytes(content)
                    print(f"[✓] Downloaded: {filename} ({len(content)} bytes)")
                    return True
                else:
                    print(f"[✗] Failed: {url} (HTTP {response.status})")
                    return False

        except asyncio.TimeoutError:
            print(f"[✗] Timeout: {url}")
            return False
        except Exception as e:
            print(f"[✗] Error downloading {url}: {e}")
            return False

async def download_images_from_backup(backup_path, output_dir, concurrency=10):
    """
    Download images from a backup file to the specified directory.
    Returns the number of successfully downloaded images.
    """
    backup_path = Path(backup_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract all image URLs
    all_urls = set()
    with open(backup_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
                if 'content' in event:
                    all_urls.update(extract_urls_from_content(event['content']))
                if 'tags' in event:
                    all_urls.update(extract_urls_from_tags(event['tags']))
            except json.JSONDecodeError:
                continue

    if not all_urls:
        return 0

    # Create a mapping file
    mapping_file = output_dir / "url_mapping.json"
    with open(mapping_file, 'w') as f:
        mapping = {url: sanitize_filename(url) for url in all_urls}
        json.dump(mapping, f, indent=2)

    # Download all images
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, url, output_dir, semaphore) for url in all_urls]
        results = await asyncio.gather(*tasks)

    return sum(results)

async def main():
    parser = argparse.ArgumentParser(description="Download images from a Nostr backup file.")
    parser.add_argument("backup_file", help="Path to the backup JSONL file")
    parser.add_argument("--output", default="images", help="Output directory for images")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent downloads")

    args = parser.parse_args()

    backup_path = Path(args.backup_file)
    if not backup_path.exists():
        print(f"[!] Backup file not found: {backup_path}")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Output directory: {output_dir}")

    # Step 1: Extract all image URLs
    print("[*] Parsing backup file for image URLs...")
    all_urls = set()
    event_count = 0

    with open(backup_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
                event_count += 1

                # Extract from content
                if 'content' in event:
                    all_urls.update(extract_urls_from_content(event['content']))

                # Extract from tags
                if 'tags' in event:
                    all_urls.update(extract_urls_from_tags(event['tags']))

            except json.JSONDecodeError:
                continue

    print(f"[*] Parsed {event_count} events")
    print(f"[*] Found {len(all_urls)} unique image URLs")

    if not all_urls:
        print("[!] No images found in backup")
        return

    # Create a mapping file
    mapping_file = output_dir / "url_mapping.json"
    with open(mapping_file, 'w') as f:
        mapping = {url: sanitize_filename(url) for url in all_urls}
        json.dump(mapping, f, indent=2)
    print(f"[*] Saved URL mapping to {mapping_file}")

    # Step 2: Download all images
    print(f"[*] Starting download of {len(all_urls)} images (concurrency: {args.concurrency})...")

    semaphore = asyncio.Semaphore(args.concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = [download_image(session, url, output_dir, semaphore) for url in all_urls]
        results = await asyncio.gather(*tasks)

    successful = sum(results)
    print(f"\n[+] Complete! Downloaded {successful}/{len(all_urls)} images to {output_dir}")

if __name__ == "__main__":
    asyncio.run(main())
