"""Command-line interface for covergen."""

from pathlib import Path
from typing import Optional

import click

from covergen.collage import CollageConfig, generate_collage
from covergen.cover_fetcher import fetch_covers_for_books
from covergen.csv_parser import parse_goodreads_csv


@click.command()
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


if __name__ == '__main__':
    main()
