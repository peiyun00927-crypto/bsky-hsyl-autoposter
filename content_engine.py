"""
Content Engine:
- Extracts metadata (OG tags, images) from www.hsylkitchen.com
- Cleans and sanitizes metadata titles & descriptions
- Generates high-converting B2B marketing copy
- Calculates UTF-8 byte facets for Bluesky links and hashtags
- Manages post queue and avoids duplicate postings
"""
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

import config

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (HSYLKitchen-Bot)"


def load_history() -> Dict[str, dict]:
    """Load previously posted URLs and metadata."""
    if config.HISTORY_FILE.exists():
        try:
            with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(url: str, post_details: dict) -> None:
    """Record a newly posted URL."""
    history = load_history()
    history[url] = {
        **post_details,
        "posted_at": datetime.now(timezone.utc).isoformat()
    }
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def load_queue() -> List[dict]:
    """Load curated post queue."""
    if config.QUEUE_FILE.exists():
        try:
            with open(config.QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def fetch_sitemap_urls() -> List[str]:
    """Fetch all crawlable URLs from sitemap.xml."""
    urls = []
    try:
        resp = requests.get(config.SITEMAP_URL, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//ns:loc", ns):
                if loc.text:
                    url = loc.text.strip()
                    if not any(ex in url for ex in ["/terms/", "/privacy/", "/contact/"]):
                        urls.append(url)
    except Exception as e:
        print(f"[!] Warning: Failed to fetch sitemap: {e}")
    return urls


def get_next_candidate() -> dict:
    """
    Select the next item to post.
    Prioritizes curated queue first, then dynamic sitemap items,
    and restarts rotation if all have been posted.
    """
    history = load_history()
    queue = load_queue()

    # 1. Check unposted items from curated queue
    for item in queue:
        if item["url"] not in history:
            return item

    # 2. Check unposted items from sitemap
    sitemap_urls = fetch_sitemap_urls()
    for url in sitemap_urls:
        if url not in history:
            return {
                "category": "sitemap_discovery",
                "url": url,
                "hook": None,
                "insight": None,
                "tags": ["#CommercialKitchen", "#FoodService", "#CentralKitchen"]
            }

    # 3. If all have been posted, restart rotation with the oldest posted curated item
    if queue:
        sorted_queue = sorted(
            queue,
            key=lambda x: history.get(x["url"], {}).get("posted_at", "")
        )
        return sorted_queue[0]

    raise RuntimeError("No candidate found to post.")


def sanitize_title(raw_title: str) -> str:
    """Clean HTML tags and brand suffixes from page titles."""
    title = re.sub(r"</?title>", "", raw_title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\|\s*HSYL.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+-\s+HSYL.*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def fetch_page_metadata(url: str) -> dict:
    """
    Extract OpenGraph / Meta details and download thumbnail for rich card preview.
    """
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "html.parser")

    # Title
    og_title = soup.find("meta", property="og:title")
    title = og_title["content"].strip() if og_title and og_title.get("content") else ""
    if not title:
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else "HSYL Kitchen Equipment"
    title = sanitize_title(title)

    # Description
    og_desc = soup.find("meta", property="og:description")
    desc = og_desc["content"].strip() if og_desc and og_desc.get("content") else ""
    if not desc:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
    if not desc:
        desc = "High-performance commercial kitchen equipment and turnkey institutional kitchen solutions."

    # Image
    og_img = soup.find("meta", property="og:image")
    img_url = og_img["content"].strip() if og_img and og_img.get("content") else ""
    if img_url:
        img_url = urllib.parse.urljoin(url, img_url)

    # Download image bytes if available
    img_bytes = None
    img_mimetype = "image/jpeg"
    if img_url:
        try:
            img_resp = requests.get(img_url, headers=headers, timeout=10)
            if img_resp.status_code == 200:
                if len(img_resp.content) <= 950_000:
                    img_bytes = img_resp.content
                    content_type = img_resp.headers.get("Content-Type", "").lower()
                    if "webp" in content_type or img_url.endswith(".webp"):
                        img_mimetype = "image/webp"
                    elif "png" in content_type or img_url.endswith(".png"):
                        img_mimetype = "image/png"
                    else:
                        img_mimetype = "image/jpeg"
        except Exception as e:
            print(f"[!] Warning: Could not download thumbnail image: {e}")

    return {
        "url": url,
        "title": title[:100],
        "description": desc[:200],
        "image_url": img_url,
        "image_bytes": img_bytes,
        "image_mimetype": img_mimetype
    }


def find_byte_range(full_text: str, target: str) -> Optional[Tuple[int, int]]:
    """
    Calculate UTF-8 byte start and end indices for Bluesky facets.
    """
    encoded_full = full_text.encode("utf-8")
    encoded_target = target.encode("utf-8")

    start_idx = encoded_full.find(encoded_target)
    if start_idx == -1:
        return None
    end_idx = start_idx + len(encoded_target)
    return start_idx, end_idx


def build_facets(text: str, url: str, tags: List[str]) -> List[dict]:
    """
    Construct AT Protocol facets for the clickable URL link and hashtags.
    """
    facets = []

    # 1. URL facet
    byte_range = find_byte_range(text, url)
    if byte_range:
        facets.append({
            "$type": "app.bsky.richtext.facet",
            "index": {
                "byteStart": byte_range[0],
                "byteEnd": byte_range[1]
            },
            "features": [
                {
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": url
                }
            ]
        })

    # 2. Hashtag facets
    for tag in tags:
        clean_tag = tag.lstrip("#")
        byte_range = find_byte_range(text, tag)
        if byte_range:
            facets.append({
                "$type": "app.bsky.richtext.facet",
                "index": {
                    "byteStart": byte_range[0],
                    "byteEnd": byte_range[1]
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#tag",
                        "tag": clean_tag
                    }
                ]
            })

    return facets


def smart_truncate(text: str, max_chars: int) -> str:
    """Truncate text at the nearest word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars - 3]
    last_space = truncated.rfind(" ")
    if last_space > int(max_chars * 0.6):
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,.;:-") + "..."


def generate_post_content(candidate: dict, metadata: dict) -> dict:
    """
    Compose high-converting B2B marketing text strictly under 285 characters,
    with embedded link facets and OpenGraph card data.
    """
    url = candidate["url"]
    tags = list(candidate.get("tags", ["#CommercialKitchen", "#FoodService", "#CentralKitchen"]))
    hook = candidate.get("hook")
    insight = candidate.get("insight")

    # Clean title
    title = sanitize_title(metadata["title"])
    metadata["title"] = title

    # Derive hook/insight dynamically if missing
    if not hook:
        if "vs" in title.lower():
            hook = f"Comparing options: {title}?"
        elif any(w in title.lower() for w in ["guide", "sizing", "selection", "checklist", "planning"]):
            hook = f"Engineering guide: {title}."
        else:
            hook = f"Commercial Kitchen Equipment: {title}."

    if not insight:
        insight = metadata["description"]

    # Target maximum text length: 280 characters
    max_len = 280
    cta_label = "Read more:"

    while len(tags) > 3:
        tags.pop()

    tag_str = " ".join(tags)
    fixed_overhead = len(hook) + len(f"\n\n\n\n👉 {cta_label} {url}\n\n{tag_str}")

    available_for_insight = max_len - fixed_overhead
    if available_for_insight < 40 and len(tags) > 2:
        tags.pop()
        tag_str = " ".join(tags)
        fixed_overhead = len(hook) + len(f"\n\n\n\n👉 {cta_label} {url}\n\n{tag_str}")
        available_for_insight = max_len - fixed_overhead

    if len(insight) > available_for_insight:
        insight = smart_truncate(insight, max(30, available_for_insight))

    draft = f"{hook}\n\n{insight}\n\n👉 {cta_label} {url}\n\n{tag_str}"

    facets = build_facets(draft, url, tags)

    return {
        "text": draft,
        "char_count": len(draft),
        "url": url,
        "facets": facets,
        "tags": tags,
        "embed_card": {
            "uri": url,
            "title": metadata["title"],
            "description": metadata["description"],
            "image_bytes": metadata.get("image_bytes"),
            "image_mimetype": metadata.get("image_mimetype", "image/jpeg")
        }
    }
