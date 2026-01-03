"""Fetch book covers from multiple APIs."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from covergen.csv_parser import Book

# Default cache directory
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "covers_cache"


def _fetch_from_open_library(isbn: str) -> Optional[bytes]:
    """Try to fetch cover from Open Library."""
    url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if len(response.content) > 1000:
            return response.content
    except Exception:
        pass
    return None


def _fetch_from_google_books(isbn: str = None, title: str = None, author: str = None) -> Optional[bytes]:
    """Try to fetch cover from Google Books API."""
    try:
        # Build search query
        if isbn:
            search_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        elif title:
            # Search by title and author
            query = f'intitle:"{title}"'
            if author:
                query += f'+inauthor:"{author}"'
            search_url = f"https://www.googleapis.com/books/v1/volumes?q={requests.utils.quote(query)}"
        else:
            return None

        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("totalItems", 0) == 0:
            return None

        # Get the first result's image links
        volume_info = data["items"][0].get("volumeInfo", {})
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
            return None

        # Google Books uses http, upgrade to https and remove zoom limit
        image_url = image_url.replace("http://", "https://")
        image_url = image_url.replace("&edge=curl", "")  # Remove curl effect
        # Try to get a larger image by modifying zoom parameter
        if "zoom=1" in image_url:
            image_url = image_url.replace("zoom=1", "zoom=3")

        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()

        if len(img_response.content) > 1000:
            return img_response.content

    except Exception:
        pass
    return None


def _get_cache_key(isbn: str = None, title: str = None, author: str = None) -> str:
    """Generate a cache key from ISBN or title+author."""
    if isbn:
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
                # Require at least 200px wide (reject placeholders)
                if img.size[0] >= 200 and img.size[1] >= 200:
                    return cache_path
                else:
                    cache_path.unlink()
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

    # Verify downloaded image - reject small/placeholder images
    try:
        with Image.open(cache_path) as img:
            # Reject images smaller than 200px wide (likely placeholders)
            if img.size[0] < 200 or img.size[1] < 200:
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
