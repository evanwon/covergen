# CLAUDE.md

This file provides guidance for Claude Code when working on this project.

## Project Overview

**covergen** is a Python CLI tool that generates book cover collage images from Goodreads CSV exports. It's used to create featured images for annual "Year in Reading" blog posts.

## Tech Stack

- **Python 3.10+**
- **Pillow** - Image manipulation and collage generation
- **requests** - HTTP requests for fetching cover images
- **click** - CLI framework

## Project Structure

```
covergen/
├── __init__.py       # Package init, version
├── __main__.py       # Entry point for `python -m covergen`
├── cli.py            # CLI argument parsing and orchestration
├── csv_parser.py     # Goodreads CSV parsing, year filtering
├── cover_fetcher.py  # Fetches covers from Open Library & Google Books
└── collage.py        # Image generation with Pillow
```

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the tool
python -m covergen <input.csv> --year 2024 -o output.png

# Run with styling
python -m covergen <input.csv> --year 2024 -o output.png --background "#1a1a2e" --columns 7
```

## Cover Fetching Logic

The tool tries multiple sources in order:
1. **Open Library** - `https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg`
2. **Google Books API** - ISBN search, then title+author fallback

Covers are cached in `covers_cache/` (gitignored). Images smaller than 200x200px are rejected as placeholders.

## Cache Filenames

- Books with ISBN: `{ISBN13}.jpg` (e.g., `9780593135204.jpg`)
- Books without ISBN: MD5 hash of `{title}-{author}` truncated to 16 chars (e.g., `3f75a3ae5859896e.jpg`)

## Common Issues

- **Missing covers**: Some books (Audible Originals, very new releases) aren't in Open Library or Google Books. Users can manually add covers to `covers_cache/`.
- **Small/placeholder images**: The tool rejects images < 200px as likely placeholders.

## Output Specifications

- Default width: 1440px (matches Ghost blog theme)
- Default columns: 7
- Book cover aspect ratio: 2:3 (width:height)
- Height auto-calculated based on book count
- Format auto-detected from extension: `.jpg`/`.jpeg` saves as JPEG (quality 90), otherwise PNG
