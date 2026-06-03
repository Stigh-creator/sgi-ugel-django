import os
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def process_image(image_field, size=(800, 800), quality=75):
    """
    Resizes and optimizes an image field if it exists on disk.
    
    Args:
        image_field: The models.ImageField instance.
        size (tuple): Maximum (width, height) dimensions.
        quality (int): JPEG/WebP quality (default 75).
    """
    if not image_field or not hasattr(image_field, 'path'):
        return
    
    img_path = image_field.path
    if os.path.exists(img_path):
        try:
            original_img = Image.open(img_path)
            image_format = (original_img.format or "").upper()
            img = ImageOps.exif_transpose(original_img)

            if img.height > size[1] or img.width > size[0]:
                img.thumbnail(size)

            save_kwargs = {"optimize": True}
            if image_format in {"JPEG", "JPG", "WEBP"}:
                save_kwargs["quality"] = quality
            if image_format in {"JPEG", "JPG"} and img.mode in {"RGBA", "P"}:
                img = img.convert("RGB")

            if image_format == "PNG":
                img.save(img_path, format="PNG", **save_kwargs)
            elif image_format == "WEBP":
                img.save(img_path, format="WEBP", **save_kwargs)
            elif image_format in {"JPEG", "JPG"}:
                img.save(img_path, format="JPEG", **save_kwargs)
            else:
                img.save(img_path, quality=quality, optimize=True)
        except Exception:
            logger.exception("Error processing image %s", img_path)
