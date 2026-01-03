"""Generate book cover collage images."""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from covergen.csv_parser import Book


@dataclass
class CollageConfig:
    """Configuration for collage generation."""
    width: int = 1440
    height: Optional[int] = None  # Auto-calculate if None
    columns: int = 7
    padding: int = 20
    margin: int = 40
    background: str = "#ffffff"
    title: Optional[str] = None
    title_color: str = "#000000"
    title_position: str = "top"  # "top" or "bottom"
    title_size: int = 48


# Standard book cover aspect ratio (width:height)
BOOK_ASPECT_RATIO = 2 / 3


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_placeholder(
    book: Book,
    width: int,
    height: int,
    bg_color: tuple[int, int, int]
) -> Image.Image:
    """
    Create a placeholder image for a missing book cover.

    Shows the book title and author on a slightly darker background.
    """
    # Create a slightly darker shade for the placeholder
    darker = tuple(max(0, c - 30) for c in bg_color)
    placeholder = Image.new('RGB', (width, height), darker)
    draw = ImageDraw.Draw(placeholder)

    # Try to load a font, with fallbacks
    font_size = max(12, width // 10)
    small_font_size = max(10, width // 14)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
        small_font = ImageFont.truetype("arial.ttf", small_font_size)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            small_font = ImageFont.truetype("DejaVuSans.ttf", small_font_size)
        except OSError:
            font = ImageFont.load_default()
            small_font = font

    # Choose text color (light if background is dark, dark if light)
    luminance = (0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2])
    text_color = (60, 60, 60) if luminance > 128 else (200, 200, 200)

    # Wrap title text to fit
    max_chars = max(10, width // (font_size // 2))
    wrapped_title = textwrap.fill(book.title, width=max_chars)
    wrapped_author = textwrap.fill(book.author, width=max_chars)

    # Calculate text positioning
    padding = width // 10

    # Draw title
    title_bbox = draw.multiline_textbbox((0, 0), wrapped_title, font=font)
    title_height = title_bbox[3] - title_bbox[1]

    author_bbox = draw.multiline_textbbox((0, 0), wrapped_author, font=small_font)
    author_height = author_bbox[3] - author_bbox[1]

    total_text_height = title_height + author_height + padding
    start_y = (height - total_text_height) // 2

    # Draw title centered
    draw.multiline_text(
        (padding, start_y),
        wrapped_title,
        fill=text_color,
        font=font
    )

    # Draw author below title
    draw.multiline_text(
        (padding, start_y + title_height + padding),
        wrapped_author,
        fill=text_color,
        font=small_font
    )

    return placeholder


def generate_collage(
    books_with_covers: list[tuple[Book, Optional[Path]]],
    config: CollageConfig,
    output_path: Path
) -> tuple[Path, list[Book]]:
    """
    Generate a collage image from book cover images.

    Args:
        books_with_covers: List of (Book, cover_path) tuples. Path is None for missing covers.
        config: Collage configuration
        output_path: Where to save the output image

    Returns:
        Tuple of (output_path, failed_books) where failed_books is a list of
        books whose cover images existed but failed to load.
    """
    if not books_with_covers:
        raise ValueError("No books provided")

    # Calculate dimensions
    num_books = len(books_with_covers)
    num_rows = math.ceil(num_books / config.columns)

    # Calculate cover dimensions
    available_width = config.width - (2 * config.margin) - ((config.columns - 1) * config.padding)
    cover_width = available_width // config.columns
    cover_height = int(cover_width / BOOK_ASPECT_RATIO)

    # Calculate title space if needed
    title_space = 0
    if config.title:
        title_space = config.title_size + config.margin

    # Calculate total height
    if config.height:
        total_height = config.height
    else:
        grid_height = (num_rows * cover_height) + ((num_rows - 1) * config.padding)
        total_height = grid_height + (2 * config.margin) + title_space

    # Create canvas
    bg_color = hex_to_rgb(config.background)
    canvas = Image.new('RGB', (config.width, total_height), bg_color)

    # Calculate starting Y position based on title position
    if config.title and config.title_position == "top":
        grid_start_y = config.margin + title_space
    else:
        grid_start_y = config.margin

    # Place covers
    failed_to_load: list[Book] = []
    for idx, (book, cover_path) in enumerate(books_with_covers):
        row = idx // config.columns
        col = idx % config.columns

        x = config.margin + (col * (cover_width + config.padding))
        y = grid_start_y + (row * (cover_height + config.padding))

        if cover_path is not None:
            try:
                with Image.open(cover_path) as cover:
                    # Resize cover maintaining aspect ratio, then crop to fit
                    cover_resized = resize_and_crop(cover, cover_width, cover_height)
                    canvas.paste(cover_resized, (x, y))
                continue
            except Exception:
                # Track books where image file exists but failed to load
                failed_to_load.append(book)

        # Create placeholder with book info
        placeholder = create_placeholder(book, cover_width, cover_height, bg_color)
        canvas.paste(placeholder, (x, y))

    # Add title if specified
    if config.title:
        draw = ImageDraw.Draw(canvas)

        # Try to use a nice font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", config.title_size)
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", config.title_size)
            except OSError:
                font = ImageFont.load_default()

        title_color = hex_to_rgb(config.title_color)

        # Calculate title position
        bbox = draw.textbbox((0, 0), config.title, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (config.width - text_width) // 2

        if config.title_position == "top":
            text_y = config.margin
        else:
            text_y = total_height - config.margin - config.title_size

        draw.text((text_x, text_y), config.title, fill=title_color, font=font)

    # Save output - auto-detect format from extension
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in ('.jpg', '.jpeg'):
        canvas.save(output_path, 'JPEG', quality=90)
    else:
        canvas.save(output_path, 'PNG')

    return output_path, failed_to_load


def resize_to_max_height(image: Image.Image, max_height: int) -> Image.Image:
    """
    Resize image to fit within max_height while maintaining aspect ratio.

    Only resizes if the image is taller than max_height.
    Returns the image at original size if already smaller.
    """
    if image.mode != 'RGB':
        image = image.convert('RGB')

    width, height = image.size
    if height <= max_height:
        return image

    ratio = max_height / height
    new_width = int(width * ratio)

    return image.resize((new_width, max_height), Image.Resampling.LANCZOS)


def resize_and_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Resize and crop an image to fit exact dimensions.
    Centers the crop to keep the most important part of the cover.
    """
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')

    img_width, img_height = image.size
    img_ratio = img_width / img_height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        # Image is wider than target - resize by height, crop width
        new_height = target_height
        new_width = int(new_height * img_ratio)
    else:
        # Image is taller than target - resize by width, crop height
        new_width = target_width
        new_height = int(new_width / img_ratio)

    # Resize
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Crop to center
    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    return resized.crop((left, top, right, bottom))
