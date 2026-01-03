"""Generate book cover collage images."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


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


def generate_collage(
    cover_paths: list[Path],
    config: CollageConfig,
    output_path: Path
) -> Path:
    """
    Generate a collage image from book cover images.

    Args:
        cover_paths: List of paths to cover images (in order)
        config: Collage configuration
        output_path: Where to save the output image

    Returns:
        Path to the generated image
    """
    if not cover_paths:
        raise ValueError("No cover images provided")

    # Calculate dimensions
    num_books = len(cover_paths)
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
    for idx, cover_path in enumerate(cover_paths):
        row = idx // config.columns
        col = idx % config.columns

        x = config.margin + (col * (cover_width + config.padding))
        y = grid_start_y + (row * (cover_height + config.padding))

        try:
            with Image.open(cover_path) as cover:
                # Resize cover maintaining aspect ratio, then crop to fit
                cover_resized = resize_and_crop(cover, cover_width, cover_height)
                canvas.paste(cover_resized, (x, y))
        except Exception as e:
            # If we can't load a cover, leave a blank space
            pass

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

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)

    return output_path


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
