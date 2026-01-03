# Book Cover Collage Generator

Generate a collage image of book covers from your Goodreads library export.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Generate collage for books read in 2024
python -m covergen generate goodreads_library_export.csv --year 2024 -o 2024-reading.png
```

### With Styling Options

```bash
python -m covergen generate goodreads_library_export.csv --year 2024 -o 2024-reading.png \
  --background "#1a1a2e" \
  --columns 7 \
  --padding 20
```

### With Title Overlay

```bash
python -m covergen generate goodreads_library_export.csv --year 2024 -o 2024-reading.png \
  --title "2024: My Year in Reading" \
  --title-color "#ffffff" \
  --background "#1a1a2e"
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--year` | Filter to books finished in this year | (all books) |
| `-o, --output` | Output image path | `collage.png` |
| `--width` | Image width in pixels | `1440` |
| `--height` | Image height (auto if omitted) | auto |
| `--columns` | Number of columns | `7` |
| `--padding` | Padding between covers (px) | `20` |
| `--margin` | Outer margin (px) | `40` |
| `--background` | Background color (hex) | `#ffffff` |
| `--title` | Title text overlay | (none) |
| `--title-color` | Title text color | `#000000` |
| `--title-position` | `top` or `bottom` | `top` |
| `--title-size` | Font size | `48` |

### Output Format

The output format is auto-detected from the file extension:

- **`.jpg` / `.jpeg`** - Saves as JPEG (quality 90). Recommended for web use—produces files 10-20x smaller than PNG with no visible quality loss.
- **`.png`** - Saves as PNG (lossless). Use if you need transparency support or lossless quality.

```bash
# Recommended: Use JPG for smaller file sizes (typically 200-500KB vs 3-5MB)
python -m covergen generate books.csv --year 2024 -o 2024-reading.jpg

# PNG if you need lossless
python -m covergen generate books.csv --year 2024 -o 2024-reading.png
```

## Exporting from Goodreads

1. Go to [Goodreads](https://www.goodreads.com) and sign in
2. Navigate to **My Books**
3. Click **Import and Export** (in the left sidebar)
4. Click **Export Library**
5. Download the CSV file

## Manually Adding Missing Covers

Some books may not have covers available through Open Library or Google Books APIs (e.g., Audible Originals, very new releases, or obscure titles). Missing covers appear as placeholders showing the book title and author.

Use the `cache-add` command to manually add covers:

```bash
# Add from a URL
python -m covergen cache-add \
  --title "The Debutante" \
  --author "Jon Ronson" \
  --url "https://example.com/cover.jpg"

# Add from a local file
python -m covergen cache-add \
  --title "The Debutante" \
  --author "Jon Ronson" \
  --file ~/Downloads/cover.jpg

# If the book has an ISBN (uses ISBN as cache key)
python -m covergen cache-add \
  --title "Some Book" \
  --author "Some Author" \
  --isbn "9780593446591" \
  --url "https://example.com/cover.jpg"
```

**Important:** The `--title` and `--author` values must match exactly how they appear in your Goodreads CSV export.

The command will:
- Download/copy the image to the cache with the correct filename
- Validate that it's a valid image file
- Warn if the image is smaller than 200x200px

After adding the cover, re-run the `generate` command and it will use your manually added cover.

## How It Works

The tool tries multiple sources to find book covers:

1. **Open Library** - Uses ISBN to fetch covers (free, no API key)
2. **Google Books** - Falls back to ISBN search, then title+author search

Covers are cached in `covers_cache/` to avoid re-downloading on subsequent runs.
