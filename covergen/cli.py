"""Command-line interface for covergen."""

from pathlib import Path
from typing import Optional

import click
import requests

from PIL import Image

from covergen.collage import CollageConfig, generate_collage, resize_to_max_height
from covergen.cover_fetcher import (
    DEFAULT_CACHE_DIR,
    _get_cache_key,
    fetch_covers_for_books,
    sanitize_filename,
)
from covergen.csv_parser import parse_goodreads_csv


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Generate book cover collages from Goodreads CSV exports."""
    # If no subcommand is given, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command('generate')
@click.argument('input_file', type=click.Path(exists=True, path_type=Path))
@click.option('-o', '--output', 'output_file', type=click.Path(path_type=Path),
              default=Path('collage.png'), help='Output image path')
@click.option('--year', type=int, default=None,
              help='Filter to books finished in this year')
@click.option('--width', type=int, default=1440,
              help='Image width in pixels')
@click.option('--height', type=int, default=None,
              help='Image height in pixels (auto-calculated if omitted)')
@click.option('--columns', type=int, default=7,
              help='Number of columns in the grid')
@click.option('--padding', type=int, default=20,
              help='Padding between covers in pixels')
@click.option('--margin', type=int, default=40,
              help='Outer margin in pixels')
@click.option('--background', type=str, default='#ffffff',
              help='Background color (hex)')
@click.option('--title', type=str, default=None,
              help='Title text overlay (optional)')
@click.option('--title-color', type=str, default='#000000',
              help='Title text color (hex)')
@click.option('--title-position', type=click.Choice(['top', 'bottom']), default='top',
              help='Title position')
@click.option('--title-size', type=int, default=48,
              help='Title font size')
def main(
    input_file: Path,
    output_file: Path,
    year: Optional[int],
    width: int,
    height: Optional[int],
    columns: int,
    padding: int,
    margin: int,
    background: str,
    title: Optional[str],
    title_color: str,
    title_position: str,
    title_size: int,
):
    """Generate a book cover collage from a Goodreads CSV export."""

    # Parse CSV
    click.echo(f"Reading {input_file}...")
    books = parse_goodreads_csv(input_file, year=year)

    if not books:
        if year:
            click.echo(f"No books found for year {year}.", err=True)
        else:
            click.echo("No books found in CSV.", err=True)
        raise SystemExit(1)

    click.echo(f"Found {len(books)} books" + (f" from {year}" if year else ""))

    # Fetch covers
    click.echo(f"Fetching {len(books)} book covers...")

    def progress_callback(completed, total):
        click.echo(f"\r  Downloaded {completed}/{total} covers", nl=False)

    results = fetch_covers_for_books(books, progress_callback=progress_callback)
    click.echo()  # Newline after progress

    # Report cover fetch results
    found_covers = [(book, path) for book, path in results if path is not None]
    missing_covers = [(book, path) for book, path in results if path is None]

    if missing_covers:
        click.echo(f"Warning: {len(missing_covers)} cover(s) not found (will show as placeholders):")
        for book, _ in missing_covers[:5]:
            click.echo(f"  - {book.title} by {book.author}")
        if len(missing_covers) > 5:
            click.echo(f"  ... and {len(missing_covers) - 5} more")

    click.echo(f"Successfully fetched {len(found_covers)} covers")

    # Generate collage
    click.echo("Generating collage...")

    config = CollageConfig(
        width=width,
        height=height,
        columns=columns,
        padding=padding,
        margin=margin,
        background=background,
        title=title,
        title_color=title_color,
        title_position=title_position,
        title_size=title_size,
    )

    output_path, failed_to_load = generate_collage(results, config, output_file)

    # Report any images that failed to load (file exists but couldn't be opened)
    if failed_to_load:
        click.echo(f"Error: {len(failed_to_load)} cached image(s) failed to load:", err=True)
        for book in failed_to_load[:5]:
            click.echo(f"  - {book.title} by {book.author}", err=True)
        if len(failed_to_load) > 5:
            click.echo(f"  ... and {len(failed_to_load) - 5} more", err=True)
        click.echo("Try deleting these from covers_cache/ and re-running.", err=True)

    click.echo(f"Collage saved to: {output_path}")


@cli.command('cache-add')
@click.option('--title', required=True, help='Book title (must match CSV exactly)')
@click.option('--author', required=True, help='Book author (must match CSV exactly)')
@click.option('--isbn', default=None, help='ISBN (if the book has one)')
@click.option('--url', default=None, help='URL to download cover image from')
@click.option('--file', 'file_path', type=click.Path(exists=True, path_type=Path),
              default=None, help='Local file path to use as cover')
@click.option('--cache-dir', type=click.Path(path_type=Path),
              default=DEFAULT_CACHE_DIR, help='Cache directory')
def cache_add(
    title: str,
    author: str,
    isbn: Optional[str],
    url: Optional[str],
    file_path: Optional[Path],
    cache_dir: Path,
):
    """Manually add a cover image to the cache.

    Use this for books where automatic fetching fails. The title and author
    must match exactly how they appear in your Goodreads CSV.

    Examples:

        # Add from URL:
        python -m covergen cache-add --title "The Debutante" --author "Jon Ronson" \\
            --url "https://example.com/cover.jpg"

        # Add from local file:
        python -m covergen cache-add --title "The Debutante" --author "Jon Ronson" \\
            --file ~/Downloads/cover.jpg

        # Add with ISBN (uses ISBN as cache key instead of hash):
        python -m covergen cache-add --title "Some Book" --author "Some Author" \\
            --isbn "9780123456789" --url "https://example.com/cover.jpg"
    """
    if not url and not file_path:
        raise click.UsageError("Either --url or --file must be provided")

    if url and file_path:
        raise click.UsageError("Cannot specify both --url and --file")

    # Generate cache key (same logic as cover_fetcher)
    cache_key = _get_cache_key(isbn=isbn, title=title, author=author)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.jpg"

    click.echo(f"Book: {title} by {author}")
    click.echo(f"Cache key: {cache_key}")

    if url:
        # Download from URL
        click.echo(f"Downloading from: {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = response.content
        except requests.RequestException as e:
            raise click.ClickException(f"Failed to download image: {e}")
    else:
        # Read from local file
        click.echo(f"Reading from: {file_path}")
        image_data = file_path.read_bytes()

    # Validate it's a valid image
    try:
        from io import BytesIO

        from PIL import Image
        with Image.open(BytesIO(image_data)) as img:
            width, height = img.size
            click.echo(f"Image size: {width}x{height}")
            if width < 200 or height < 200:
                click.echo("Warning: Image is smaller than 200x200px, may appear low quality")
    except Exception as e:
        raise click.ClickException(f"Invalid image file: {e}")

    # Save to cache
    cache_path.write_bytes(image_data)
    click.echo(f"Saved to: {cache_path}")
    click.echo("Done! The cover will be used next time you generate a collage.")


@cli.command('clear-cache')
@click.option('--cache-dir', type=click.Path(path_type=Path),
              default=DEFAULT_CACHE_DIR, help='Cache directory')
@click.option('--dry-run', is_flag=True,
              help='Show what would be deleted without actually deleting')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
def clear_cache(cache_dir: Path, dry_run: bool):
    """Clear all cached cover images.

    This removes all downloaded cover images from the cache directory.
    Use --dry-run to see what would be deleted without actually deleting.

    Examples:

        # Clear the cache:
        python -m covergen clear-cache

        # Preview what would be deleted:
        python -m covergen clear-cache --dry-run
    """
    if not cache_dir.exists():
        click.echo("Cache directory does not exist. Nothing to clear.")
        return

    # Find all image files in cache
    image_files = list(cache_dir.glob("*.jpg")) + list(cache_dir.glob("*.png"))

    if not image_files:
        click.echo("Cache is already empty.")
        return

    # Calculate total size
    total_size = sum(f.stat().st_size for f in image_files)
    size_mb = total_size / (1024 * 1024)

    if dry_run:
        click.echo(f"Would delete {len(image_files)} cached image(s) ({size_mb:.2f} MB):")
        for f in image_files[:10]:
            click.echo(f"  - {f.name}")
        if len(image_files) > 10:
            click.echo(f"  ... and {len(image_files) - 10} more")
    else:
        for f in image_files:
            f.unlink()
        click.echo(f"Deleted {len(image_files)} cached image(s) ({size_mb:.2f} MB)")


@cli.command('export-thumbnails')
@click.argument('input_file', type=click.Path(exists=True, path_type=Path))
@click.option('-o', '--output-dir', type=click.Path(path_type=Path),
              default=Path('thumbnails'), help='Output directory for thumbnails')
@click.option('--year', type=int, default=None,
              help='Filter to books finished in this year')
@click.option('--max-height', type=int, default=600,
              help='Maximum height in pixels (width scales proportionally)')
@click.option('--format', 'output_format', type=click.Choice(['jpg', 'png']),
              default='jpg', help='Output image format')
@click.option('--quality', type=int, default=90,
              help='JPEG quality (1-100, ignored for PNG)')
def export_thumbnails(
    input_file: Path,
    output_dir: Path,
    year: Optional[int],
    max_height: int,
    output_format: str,
    quality: int,
):
    """Export individual book cover thumbnails for blog use.

    Resizes covers to a maximum height while maintaining aspect ratio.
    Useful for embedding individual book images in blog posts.

    Examples:

        # Export all covers to thumbnails/ directory:
        python -m covergen export-thumbnails goodreads.csv

        # Export 2024 books with custom height:
        python -m covergen export-thumbnails goodreads.csv --year 2024 --max-height 400

        # Export to a specific directory:
        python -m covergen export-thumbnails goodreads.csv -o ~/blog/images/books
    """
    # Parse CSV
    click.echo(f"Reading {input_file}...")
    books = parse_goodreads_csv(input_file, year=year)

    if not books:
        if year:
            click.echo(f"No books found for year {year}.", err=True)
        else:
            click.echo("No books found in CSV.", err=True)
        raise SystemExit(1)

    click.echo(f"Found {len(books)} books" + (f" from {year}" if year else ""))

    # Fetch covers (uses cache)
    click.echo(f"Fetching {len(books)} book covers...")

    def progress_callback(completed, total):
        click.echo(f"\r  Downloaded {completed}/{total} covers", nl=False)

    results = fetch_covers_for_books(books, progress_callback=progress_callback)
    click.echo()  # Newline after progress

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export each cover
    exported = 0
    skipped_books = []
    small_images = []
    warn_threshold = int(max_height * 2 / 3)  # Warn if less than 2/3 of requested height

    for book, cover_path in results:
        if cover_path is None:
            skipped_books.append((book, "no cover available"))
            continue

        try:
            with Image.open(cover_path) as img:
                resized = resize_to_max_height(img, max_height)

                # Track images that are smaller than expected
                if resized.height < warn_threshold:
                    small_images.append((book, resized.height))

                # Generate filename using same logic as cache
                filename = sanitize_filename(book.title)
                if book.best_isbn:
                    filename = f"{book.best_isbn}-{filename}"

                output_path = output_dir / f"{filename}.{output_format}"

                if output_format == 'jpg':
                    resized.save(output_path, 'JPEG', quality=quality)
                else:
                    resized.save(output_path, 'PNG')

                exported += 1
        except Exception as e:
            skipped_books.append((book, str(e)))

    click.echo(f"Exported {exported} thumbnails to {output_dir}/")
    if skipped_books:
        click.echo(f"Skipped {len(skipped_books)} books:")
        for book, reason in skipped_books:
            click.echo(f"  - {book.title} by {book.author}: {reason}")
    if small_images:
        click.echo(f"Warning: {len(small_images)} image(s) smaller than {warn_threshold}px height:")
        for book, height in small_images[:5]:
            click.echo(f"  - {book.title} ({height}px)")
        if len(small_images) > 5:
            click.echo(f"  ... and {len(small_images) - 5} more")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
