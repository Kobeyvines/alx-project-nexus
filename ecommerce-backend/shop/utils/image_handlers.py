"""
Utility functions for handling product images.
"""
import os
from io import BytesIO
from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

def validate_image(image):
    """
    Validate image dimensions, size, and format.
    """
    try:
        img = Image.open(image)
    except Exception as e:
        raise ValidationError(f"Invalid image file: {str(e)}")

    # Check format
    if img.format.upper() not in settings.PRODUCT_IMAGE_FORMATS:
        raise ValidationError(
            f"Unsupported image format. Supported formats: {', '.join(settings.PRODUCT_IMAGE_FORMATS)}"
        )

    # Check dimensions
    if (img.width < settings.PRODUCT_IMAGE_MIN_DIMENSIONS[0] or
            img.height < settings.PRODUCT_IMAGE_MIN_DIMENSIONS[1]):
        raise ValidationError(
            f"Image dimensions too small. Minimum dimensions: {settings.PRODUCT_IMAGE_MIN_DIMENSIONS}"
        )
    
    if (img.width > settings.PRODUCT_IMAGE_MAX_DIMENSIONS[0] or
            img.height > settings.PRODUCT_IMAGE_MAX_DIMENSIONS[1]):
        raise ValidationError(
            f"Image dimensions too large. Maximum dimensions: {settings.PRODUCT_IMAGE_MAX_DIMENSIONS}"
        )

    # Check file size
    if image.size > settings.PRODUCT_IMAGE_MAX_SIZE:
        max_size_mb = settings.PRODUCT_IMAGE_MAX_SIZE / (1024 * 1024)
        raise ValidationError(f"Image file too large. Maximum size: {max_size_mb}MB")

def process_product_image(image):
    """
    Process the product image:
    1. Validate the image
    2. Convert to RGB if needed
    3. Optimize for web
    4. Create thumbnails
    """
    validate_image(image)
    
    # Open and process image
    img = Image.open(image)
    
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Process main image
    main_image = optimize_image(img)
    
    # Create thumbnails
    thumbnails = {}
    for size_name, dimensions in settings.PRODUCT_IMAGE_THUMBNAILS.items():
        thumbnails[size_name] = create_thumbnail(img, dimensions)
    
    return main_image, thumbnails

def optimize_image(img, quality=85):
    """
    Optimize image for web delivery:
    1. Convert to JPEG format
    2. Optimize quality
    3. Strip metadata
    """
    output = BytesIO()
    
    # Save with optimization
    img.save(
        output,
        format='JPEG',
        quality=quality,
        optimize=True,
        progressive=True
    )
    
    # Prepare for saving
    output.seek(0)
    
    return output

def create_thumbnail(img, size):
    """
    Create a thumbnail of the specified size while maintaining aspect ratio.
    """
    # Calculate new dimensions maintaining aspect ratio
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    # Optimize thumbnail
    return optimize_image(img, quality=85)

def save_product_image(instance, image, filename):
    """
    Save product image and its thumbnails.
    Returns paths to all saved images.
    """
    # Process main image and create thumbnails
    main_image, thumbnails = process_product_image(image)
    
    # Prepare base path
    base_name = os.path.splitext(filename)[0]
    base_path = f'products/{instance.id}/{base_name}'
    
    # Save main image
    main_path = f'{base_path}.jpg'
    instance.image.save(
        main_path,
        InMemoryUploadedFile(
            main_image,
            None,
            main_path,
            'image/jpeg',
            main_image.tell(),
            None
        ),
        save=False
    )
    
    # Save thumbnails
    thumbnail_paths = {}
    for size_name, thumb_data in thumbnails.items():
        thumb_path = f'{base_path}_{size_name}.jpg'
        thumbnail_paths[size_name] = thumb_path
        
        getattr(instance, f'image_thumbnail_{size_name}').save(
            thumb_path,
            InMemoryUploadedFile(
                thumb_data,
                None,
                thumb_path,
                'image/jpeg',
                thumb_data.tell(),
                None
            ),
            save=False
        )
    
    return main_path, thumbnail_paths