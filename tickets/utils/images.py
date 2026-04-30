import os
from PIL import Image

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
            img = Image.open(img_path)
            # Solo redimensiona si es más grande que el límite
            if img.height > size[1] or img.width > size[0]:
                img.thumbnail(size)
                # Calidad optimizada para reducir el peso
                img.save(img_path, quality=quality, optimize=True)
            elif quality < 100:
                # Incluso si no se redimensiona, guardar con calidad optimizada
                img.save(img_path, quality=quality, optimize=True)
        except Exception as e:
            # Log error or handle gracefully
            print(f"Error processing image {img_path}: {e}")
