#!/usr/bin/env python3
"""
Bluesky Daily Auto-Poster for HSYL Kitchen Equipment (www.hsylkitchen.com).
Builds backlinks and generates B2B marketing value on Bluesky (bsky.app).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests

import config
import content_engine


class BlueskyClient:
    def __init__(self, handle: str, password: str, service_url: str = "https://bsky.social"):
        self.handle = handle
        self.password = password
        self.service_url = service_url.rstrip("/")
        self.access_jwt: Optional[str] = None
        self.did: Optional[str] = None

    def login(self) -> bool:
        """Authenticate with Bluesky using handle and App Password."""
        url = f"{self.service_url}/xrpc/com.atproto.server.createSession"
        payload = {
            "identifier": self.handle,
            "password": self.password
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            self.access_jwt = data["accessJwt"]
            self.did = data["did"]
            print(f"[✓] Successfully authenticated as DID: {self.did}")
            return True
        else:
            print(f"[✗] Login failed ({resp.status_code}): {resp.text}")
            return False

    def upload_blob(self, image_bytes: bytes, mimetype: str) -> Optional[dict]:
        """Upload thumbnail image to AT Protocol blob storage."""
        if not self.access_jwt:
            return None

        url = f"{self.service_url}/xrpc/com.atproto.repo.uploadBlob"
        headers = {
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": mimetype
        }
        resp = requests.post(url, headers=headers, data=image_bytes, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("blob")
        else:
            print(f"[!] Warning: Blob upload failed ({resp.status_code}): {resp.text}")
            return None

    def create_post(self, text: str, facets: list, embed_card: dict) -> dict:
        """Publish post with rich text facets and external link card embed."""
        if not self.access_jwt or not self.did:
            raise RuntimeError("Must login before posting.")

        # 1. Upload thumbnail blob if image is present
        thumb_blob = None
        if embed_card.get("image_bytes"):
            print(f"[*] Uploading thumbnail blob ({len(embed_card['image_bytes'])} bytes)...")
            thumb_blob = self.upload_blob(
                embed_card["image_bytes"],
                embed_card.get("image_mimetype", "image/jpeg")
            )

        # 2. Build external embed card
        external = {
            "uri": embed_card["uri"],
            "title": embed_card["title"],
            "description": embed_card["description"]
        }
        if thumb_blob:
            external["thumb"] = thumb_blob

        embed = {
            "$type": "app.bsky.embed.external",
            "external": external
        }

        # 3. Build post record
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now_utc,
            "embed": embed
        }
        if facets:
            record["facets"] = facets

        # 4. Send request to createRecord
        url = f"{self.service_url}/xrpc/com.atproto.repo.createRecord"
        headers = {
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": "application/json"
        }
        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.post",
            "record": record
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()


def print_dry_run_preview(post_data: dict, metadata: dict) -> None:
    """Print formatted post preview for testing and dry runs."""
    print("\n" + "=" * 65)
    print("🚀 [DRY-RUN PREVIEW] Bluesky Post Simulation")
    print("=" * 65)
    print(f"Target URL   : {post_data['url']}")
    print(f"Char Count   : {post_data['char_count']} / {config.MAX_POST_CHARS} (Limit)")
    print(f"Facets Count : {len(post_data['facets'])} (URL + Hashtags)")
    print("-" * 65)
    print("📝 POST TEXT:")
    print(post_data["text"])
    print("-" * 65)
    print("🎴 EXTERNAL LINK CARD EMBED:")
    print(f"  Title      : {metadata['title']}")
    print(f"  Description: {metadata['description']}")
    print(f"  Image URL  : {metadata.get('image_url') or 'None'}")
    img_size = len(metadata["image_bytes"]) if metadata.get("image_bytes") else 0
    print(f"  Image Size : {img_size} bytes ({metadata.get('image_mimetype', 'N/A')})")
    print("-" * 65)
    print("🔍 FACETS (AT PROTOCOL UTF-8 BYTE RANGES):")
    for idx, f in enumerate(post_data["facets"], 1):
        feat = f["features"][0]
        f_type = feat.get("$type", "").split("#")[-1]
        target = feat.get("uri") or feat.get("tag")
        b_start = f["index"]["byteStart"]
        b_end = f["index"]["byteEnd"]
        print(f"  [{idx}] {f_type.upper()}: '{target}' (bytes {b_start}..{b_end})")
    print("=" * 65 + "\n")


def execute_post_task(force_url: Optional[str] = None, dry_run: bool = False) -> bool:
    """Run one single post cycle."""
    print(f"\n[*] Starting Bluesky posting cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Determine candidate
    if force_url:
        candidate = {
            "category": "custom_override",
            "url": force_url,
            "hook": "Engineered for high-volume commercial kitchen performance.",
            "insight": "Explore technical parameters, workflow layouts, and turnkey equipment.",
            "tags": ["#CommercialKitchen", "#FoodService", "#CentralKitchen"]
        }
    else:
        candidate = content_engine.get_next_candidate()

    target_url = candidate["url"]
    print(f"[*] Selected candidate URL: {target_url} (Category: {candidate.get('category')})")

    # 2. Fetch page metadata & image
    print("[*] Fetching page OpenGraph metadata...")
    metadata = content_engine.fetch_page_metadata(target_url)

    # 3. Generate marketing copy & facets
    post_data = content_engine.generate_post_content(candidate, metadata)

    # 4. Check if dry-run
    if dry_run or config.DRY_RUN:
        print("[i] Dry-run enabled. Skipping actual API post.")
        print_dry_run_preview(post_data, metadata)
        return True

    # 5. Check credentials
    if not config.BSKY_HANDLE or not config.BSKY_APP_PASSWORD:
        print("[!] Error: BSKY_HANDLE or BSKY_APP_PASSWORD not configured!")
        print("[i] Showing dry-run preview instead:")
        print_dry_run_preview(post_data, metadata)
        return False

    # 6. Authenticate & Post
    client = BlueskyClient(
        handle=config.BSKY_HANDLE,
        password=config.BSKY_APP_PASSWORD,
        service_url=config.BSKY_SERVICE_URL
    )

    if not client.login():
        return False

    print("[*] Publishing post to Bluesky...")
    result = client.create_post(
        text=post_data["text"],
        facets=post_data["facets"],
        embed_card=post_data["embed_card"]
    )

    post_uri = result.get("uri", "")
    print(f"[✓] Post successfully published!")
    print(f"    Post URI: {post_uri}")

    # Construct public post URL if possible (e.g. https://bsky.app/profile/<handle>/post/<rkey>)
    rkey = post_uri.split("/")[-1] if post_uri else ""
    if rkey:
        print(f"    View on Bluesky: https://bsky.app/profile/{config.BSKY_HANDLE}/post/{rkey}")

    # 7. Record to history
    content_engine.save_history(target_url, {
        "post_uri": post_uri,
        "cid": result.get("cid"),
        "title": metadata["title"],
        "category": candidate.get("category")
    })
    print(f"[✓] Saved to posted_history.json")
    return True


def main():
    parser = argparse.ArgumentParser(description="Bluesky Daily Marketing Auto-Poster for HSYL Kitchen")
    parser.add_argument("--dry-run", action="store_true", help="Simulate post generation without calling Bluesky API")
    parser.add_argument("--force-url", type=str, help="Specify exact URL to post")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background with a daily interval")
    parser.add_argument("--interval-hours", type=float, default=24.0, help="Interval in hours for daemon mode (default: 24)")

    args = parser.parse_args()

    if args.daemon:
        interval_secs = int(args.interval_hours * 3600)
        print(f"[*] Running in daemon mode (interval: {args.interval_hours} hours / {interval_secs}s)...")
        while True:
            try:
                execute_post_task(force_url=args.force_url, dry_run=args.dry_run)
            except Exception as e:
                print(f"[!] Execution error in loop: {e}")
            print(f"[*] Sleeping for {args.interval_hours} hours...")
            time.sleep(interval_secs)
    else:
        success = execute_post_task(force_url=args.force_url, dry_run=args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
