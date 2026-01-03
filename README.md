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
python -m covergen goodreads_library_export.csv --year 2024 -o 2024-reading.png
```

### With Styling Options

```bash
python -m covergen goodreads_library_export.csv --year 2024 -o 2024-reading.png \
  --background "#1a1a2e" \
  --columns 7 \
  --padding 20
```

### With Title Overlay

```bash
python -m covergen goodreads_library_export.csv --year 2024 -o 2024-reading.png \
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
python -m covergen books.csv --year 2024 -o 2024-reading.jpg

# PNG if you need lossless
python -m covergen books.csv --year 2024 -o 2024-reading.png
```

## Exporting from Goodreads

1. Go to [Goodreads](https://www.goodreads.com) and sign in
2. Navigate to **My Books**
3. Click **Import and Export** (in the left sidebar)
4. Click **Export Library**
5. Download the CSV file

## Manually Adding Missing Covers

Some books may not have covers available through Open Library or Google Books APIs (e.g., Audible Originals, very new releases, or obscure titles). Missing covers appear as placeholders showing the book title and author, making it easy to identify which books need manual intervention.

### Process

1. **Run the tool first** to identify which covers are missing:
   ```bash
   python -m covergen your_export.csv --year 2024 -o output.png
   ```
   The tool will list any books where covers couldn't be found, and the output image will show placeholders with book titles.

2. **Find the book's ISBN** in your Goodreads export CSV:
   - Open the CSV in a spreadsheet application
   - Find the book by title
   - Note the `ISBN13` column value (e.g., `9780593446591`)

3. **Download a cover image**:
   - Search for the book cover on the publisher's website, Amazon, or Audible
   - Save the image (right-click → Save Image As)
   - Recommended: at least 300px wide for good quality

4. **Add to the cache**:
   - Rename the image to match the ISBN: `{ISBN13}.jpg`
   - Place it in the `covers_cache/` folder

   Example:
   ```
   covers_cache/9780593446591.jpg
   ```

5. **For books without ISBN** (shows as hash in cache):
   - The tool uses a hash of `{title}-{author}` for caching
   - Run with `--verbose` or check the warning output to see the title
   - You can name the file using the ISBN if you look it up, or use the existing hash pattern

6. **Re-run the tool** - it will use your manually added cover:
   ```bash
   python -m covergen your_export.csv --year 2024 -o output.png
   ```

### Example: Adding an Audible Original

For "The Debutante" by Jon Ronson (an Audible Original):

1. Find the ISBN: `9780593446591` (from Goodreads CSV)
2. Go to Audible and find the book cover image
3. Save as `covers_cache/9780593446591.jpg`
4. Re-run the collage generator

## How It Works

The tool tries multiple sources to find book covers:

1. **Open Library** - Uses ISBN to fetch covers (free, no API key)
2. **Google Books** - Falls back to ISBN search, then title+author search

Covers are cached in `covers_cache/` to avoid re-downloading on subsequent runs.
