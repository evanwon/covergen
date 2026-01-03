"""Fetch book covers from multiple APIs."""

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from covergen.csv_parser import Book


# Default cache directory
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "covers_cache"


def sanitize_filename(title: str, max_length: int = 60) -> str:
    """
    Generate a filesystem-safe filename from a book title.

    Removes special characters, replaces spaces with hyphens,
    and truncates to max_length.
    """
    # Remove characters that are problematic on Windows/Unix filesystems
    clean = re.sub(r'[/\\:*?"<>|]', '', title)
    # Replace spaces and multiple whitespace with single hyphen
    clean = re.sub(r'\s+', '-', clean)
    # Collapse multiple hyphens
    clean = re.sub(r'-+', '-', clean)
    # Remove leading/trailing hyphens
    clean = clean.strip('-')
    # Lowercase for consistency
    clean = clean.lower()
    # Truncate if needed (avoid cutting in middle of a word if possible)
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip('-')
    return clean


def _is_placeholder_image(img: Image.Image) -> bool:
    """
    Detect "image not available" placeholder images from Google Books.

    These placeholders are mostly solid gray/white with simple text,
    resulting in very few unique colors compared to real book covers.
    """
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Sample pixels from the image
    pixels = list(img.getdata())
    sample_size = min(1000, len(pixels))
    step = max(1, len(pixels) // sample_size)
    sampled = pixels[::step]

    # Count unique colors (quantized to reduce noise)
    def quantize(pixel):
        return (pixel[0] // 32, pixel[1] // 32, pixel[2] // 32)

    unique_colors = set(quantize(p) for p in sampled)

    # Placeholder images typically have < 15 unique quantized colors
    # Real book covers usually have 50+ unique colors
    return len(unique_colors) < 15


def _fetch_from_open_library(isbn: str, min_size: int = 200) -> Optional[bytes]:
    """Try to fetch cover from Open Library.

    Args:
        isbn: The ISBN to look up
        min_size: Minimum width/height in pixels (images smaller than this are rejected)
    """
    # First, check if Open Library has a cover for this ISBN via their Books API
    # This avoids downloading placeholder images
    try:
        api_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        api_response = requests.get(api_url, timeout=10)
        api_response.raise_for_status()
        data = api_response.json()

        # If no data returned, they don't have this book
        book_key = f"ISBN:{isbn}"
        if book_key not in data:
            return None

        # Check if cover info exists
        book_data = data[book_key]
        if "cover" not in book_data:
            return None

        # Use the large cover URL from API response (guaranteed to be real)
        cover_url = book_data["cover"].get("large") or book_data["cover"].get("medium")
        if not cover_url:
            return None

        img_response = requests.get(cover_url, timeout=10)
        img_response.raise_for_status()
        if len(img_response.content) > 1000:
            # Validate image dimensions before returning
            # Open Library sometimes returns small thumbnails even for "-L.jpg" URLs
            with Image.open(BytesIO(img_response.content)) as img:
                if img.size[0] < min_size or img.size[1] < min_size:
                    return None  # Too small, let caller try other sources
            return img_response.content

    except Exception:
        pass
    return None


def _fetch_from_google_books(
    isbn: str = None,
    title: str = None,
    author: str = None,
    min_size: int = 200
) -> Optional[bytes]:
    """Try to fetch cover from Google Books API.

    Args:
        isbn: ISBN to search for (tried first if provided)
        title: Book title (used if ISBN fails or not provided)
        author: Book author (used with title)
        min_size: Minimum image dimension in pixels

    Returns:
        Image bytes if a valid cover is found, None otherwise.
    """
    def try_search(search_url: str) -> Optional[bytes]:
        """Try a Google Books search and return valid cover image bytes."""
        try:
            response = requests.get(search_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("totalItems", 0) == 0:
                return None

            # Try multiple results in case first ones are placeholders
            for item in data.get("items", [])[:5]:
                volume_info = item.get("volumeInfo", {})
                image_links = volume_info.get("imageLinks", {})

                # Prefer larger images
                image_url = (
                    image_links.get("extraLarge") or
                    image_links.get("large") or
                    image_links.get("medium") or
                    image_links.get("thumbnail") or
                    image_links.get("smallThumbnail")
                )

                if not image_url:
                    continue

                # Google Books uses http, upgrade to https and remove zoom limit
                image_url = image_url.replace("http://", "https://")
                image_url = image_url.replace("&edge=curl", "")  # Remove curl effect
                # Try to get a larger image by modifying zoom parameter
                if "zoom=1" in image_url:
                    image_url = image_url.replace("zoom=1", "zoom=3")

                try:
                    img_response = requests.get(image_url, timeout=10)
                    img_response.raise_for_status()

                    if len(img_response.content) <= 1000:
                        continue

                    # Validate image is not a placeholder
                    with Image.open(BytesIO(img_response.content)) as img:
                        # Check size
                        if img.size[0] < min_size or img.size[1] < min_size:
                            continue
                        # Check for placeholder (low color count)
                        if _is_placeholder_image(img):
                            continue

                    return img_response.content
                except Exception:
                    continue

        except Exception:
            pass
        return None

    # Try ISBN search first if provided
    if isbn:
        search_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        result = try_search(search_url)
        if result:
            return result

    # Fall back to title/author search
    if title:
        query = f'intitle:"{title}"'
        if author:
            query += f'+inauthor:"{author}"'
        search_url = f"https://www.googleapis.com/books/v1/volumes?q={requests.utils.quote(query)}"
        return try_search(search_url)

    return None


def _get_cache_key(isbn: str = None, title: str = None, author: str = None) -> str:
    """
    Generate a cache key from ISBN and/or title.

    Format:
    - With ISBN: "{isbn}-{sanitized-title}" (e.g., "9780743273565-the-great-gatsby")
    - Without ISBN: "{hash}" (MD5 hash of title+author, truncated to 16 chars)
    """
    if isbn:
        if title:
            sanitized = sanitize_filename(title, max_length=50)
            return f"{isbn}-{sanitized}"
        return isbn
    # Use a hash of title+author for non-ISBN lookups
    key = f"{title or ''}-{author or ''}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def fetch_cover(
    cache_dir: Path,
    isbn: str = None,
    title: str = None,
    author: str = None
) -> Optional[Path]:
    """
    Fetch a book cover, trying multiple sources.

    Args:
        cache_dir: Directory to cache downloaded covers
        isbn: The ISBN (10 or 13) of the book (preferred)
        title: Book title (used if no ISBN)
        author: Book author (used with title)

    Returns:
        Path to the cover image, or None if not found
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _get_cache_key(isbn, title, author)
    cache_path = cache_dir / f"{cache_key}.jpg"

    # Return cached version if exists and valid
    if cache_path.exists():
        try:
            with Image.open(cache_path) as img:
                # Reject small images
                if img.size[0] < 200 or img.size[1] < 200:
                    cache_path.unlink()
                # Reject "image not available" style placeholders
                elif _is_placeholder_image(img):
                    cache_path.unlink()
                else:
                    return cache_path
        except Exception:
            cache_path.unlink(missing_ok=True)

    # Try multiple sources
    image_data = None

    if isbn:
        # Try Open Library first (only works with ISBN)
        image_data = _fetch_from_open_library(isbn)

        # Fall back to Google Books with ISBN
        if not image_data:
            image_data = _fetch_from_google_books(isbn=isbn)

    # Fall back to Google Books with title/author
    if not image_data and title:
        image_data = _fetch_from_google_books(title=title, author=author)

    if not image_data:
        return None

    # Save to cache
    cache_path.write_bytes(image_data)

    # Verify downloaded image - reject placeholder images
    try:
        with Image.open(cache_path) as img:
            # Reject images smaller than 200px
            if img.size[0] < 200 or img.size[1] < 200:
                cache_path.unlink()
                return None
            # Reject "image not available" style placeholders (mostly from Google Books)
            if _is_placeholder_image(img):
                cache_path.unlink()
                return None
    except Exception:
        cache_path.unlink(missing_ok=True)
        return None

    return cache_path


def fetch_covers_for_books(
    books: list[Book],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    max_workers: int = 5,
    progress_callback=None
) -> list[tuple[Book, Optional[Path]]]:
    """
    Fetch covers for a list of books in parallel.

    Args:
        books: List of Book objects
        cache_dir: Directory to cache downloaded covers
        max_workers: Number of parallel download threads
        progress_callback: Optional callback(completed, total) for progress

    Returns:
        List of (Book, cover_path) tuples. cover_path is None if not found.
    """
    results = []
    total = len(books)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all fetch tasks
        future_to_book = {}
        for book in books:
            future = executor.submit(
                fetch_cover,
                cache_dir,
                isbn=book.best_isbn,
                title=book.title,
                author=book.author
            )
            future_to_book[future] = book

        # Collect results as they complete
        for future in as_completed(future_to_book):
            book = future_to_book[future]
            try:
                cover_path = future.result()
                results.append((book, cover_path))
            except Exception:
                results.append((book, None))

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    return results
