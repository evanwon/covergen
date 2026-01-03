"""Parse Goodreads CSV export files."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Book:
    """Represents a book from Goodreads export."""
    title: str
    author: str
    isbn: Optional[str]
    isbn13: Optional[str]
    date_read: Optional[str]

    @property
    def best_isbn(self) -> Optional[str]:
        """Return ISBN13 if available, otherwise ISBN10."""
        # Clean up ISBNs - Goodreads wraps them in ="..."
        isbn13 = self._clean_isbn(self.isbn13)
        isbn = self._clean_isbn(self.isbn)
        return isbn13 or isbn

    @staticmethod
    def _clean_isbn(value: Optional[str]) -> Optional[str]:
        """Remove Goodreads formatting from ISBN values."""
        if not value:
            return None
        # Remove ="..." wrapper that Goodreads uses
        cleaned = value.strip().strip('="').strip('"')
        if not cleaned or cleaned == "":
            return None
        return cleaned


def parse_goodreads_csv(
    filepath: Path,
    year: Optional[int] = None
) -> list[Book]:
    """
    Parse a Goodreads CSV export and return list of books.

    Args:
        filepath: Path to the Goodreads CSV export file
        year: Optional year to filter by (based on Date Read)

    Returns:
        List of Book objects
    """
    books = []

    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            book = Book(
                title=row.get('Title', ''),
                author=row.get('Author', ''),
                isbn=row.get('ISBN', ''),
                isbn13=row.get('ISBN13', ''),
                date_read=row.get('Date Read', ''),
            )

            # Filter by year if specified
            if year is not None:
                if not book.date_read:
                    continue
                # Date Read format is YYYY/MM/DD
                try:
                    read_year = int(book.date_read.split('/')[0])
                    if read_year != year:
                        continue
                except (ValueError, IndexError):
                    continue

            books.append(book)

    return books
