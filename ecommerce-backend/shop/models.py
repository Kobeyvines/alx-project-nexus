from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from shop.utils.image_handlers import validate_image

class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]
        verbose_name = 'category'
        verbose_name_plural = 'categories'
        
    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, db_index=True, unique=False)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    reorder_point = models.PositiveIntegerField(default=20)
    available = models.BooleanField(default=True)
    
    # Image fields
    image = models.ImageField(
        upload_to='products/%Y/%m/%d',
        blank=True,
        null=True,
        help_text='Main product image'
    )
    image_thumbnail_small = models.ImageField(
        upload_to='products/%Y/%m/%d/thumbnails',
        blank=True,
        null=True,
        help_text='Small thumbnail (100x100)'
    )
    image_thumbnail_medium = models.ImageField(
        upload_to='products/%Y/%m/%d/thumbnails',
        blank=True,
        null=True,
        help_text='Medium thumbnail (300x300)'
    )
    image_thumbnail_large = models.ImageField(
        upload_to='products/%Y/%m/%d/thumbnails',
        blank=True,
        null=True,
        help_text='Large thumbnail (600x600)'
    )
    
    # Rating fields
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text='Average rating (0-5)'
    )
    total_reviews = models.PositiveIntegerField(
        default=0,
        help_text='Total number of reviews'
    )
    
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    last_stock_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['id', 'name']),
            models.Index(fields=['slug']),
            models.Index(fields=['-created'])
        ]
        
    def __str__(self):
        return self.name
    
    @property
    def in_stock(self):
        return self.stock > 0 and self.available
    
    @property
    def needs_restock(self):
        return self.stock <= self.reorder_point
        
    @property
    def low_stock(self):
        return self.stock <= self.low_stock_threshold
        
    def adjust_stock(self, quantity, operation='remove'):
        """
        Adjust stock level
        :param quantity: Amount to add or remove
        :param operation: 'add' or 'remove'
        :return: True if successful, False if insufficient stock
        """
        if operation == 'remove':
            if self.stock >= quantity:
                self.stock -= quantity
                self.last_stock_update = timezone.now()
                self.save()
                return True
            return False
        elif operation == 'add':
            self.stock += quantity
            self.last_stock_update = timezone.now()
            self.save()
            return True
        return False
        
    def process_and_save_image(self, image_file):
        """
        Process and save product image with thumbnails
        """
        from shop.utils.image_handlers import save_product_image
        
        if image_file:
            # Delete old images if they exist
            self.delete_images()
            
            # Save new images
            try:
                main_path, thumbnail_paths = save_product_image(
                    self, image_file, image_file.name
                )
                self.save()
                return True
            except ValidationError as e:
                # Re-raise the validation error
                raise e
            except Exception as e:
                # Log the error and raise a validation error
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing image for product {self.id}: {str(e)}")
                raise ValidationError("Error processing image. Please try again.")
        
        return False
    
    def delete_images(self):
        """
        Delete all associated images
        """
        if self.image:
            self.image.delete(save=False)
        if self.image_thumbnail_small:
            self.image_thumbnail_small.delete(save=False)
        if self.image_thumbnail_medium:
            self.image_thumbnail_medium.delete(save=False)
        if self.image_thumbnail_large:
            self.image_thumbnail_large.delete(save=False)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Cart(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("checked_out", "Checked Out"),
        ("abandoned", "Abandoned"),
    )

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="cart"
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_price(self):
        return sum(item.subtotal() for item in self.items.all())
    
    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    def checkout(self):
        """
        Checkout process with stock validation and management
        Returns (success, message)
        """
        # Check stock availability for all items
        for item in self.items.all():
            if not item.product.available:
                return False, f"Product {item.product.name} is not available"
            if item.quantity > item.product.stock:
                return False, f"Insufficient stock for {item.product.name}"
        
        # Create order and adjust stock
        order = Order.objects.create(
            user=self.user,
            total_amount=self.total_price()
        )
        
        # Process each item
        for item in self.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
            # Adjust stock
            item.product.adjust_stock(item.quantity, 'remove')
        
        # Mark cart as checked out
        self.status = "checked_out"
        self.save()
        
        return True, order

    def __str__(self):
        return f"Cart {self.id} - {self.user.username} ({self.status})"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "product")

    def subtotal(self):
        return self.product.price * self.quantity

    def clean(self):
        """Validate stock availability"""
        if self.quantity > self.product.stock:
            raise ValidationError(f"Only {self.product.stock} items available in stock")
        if not self.product.available:
            raise ValidationError("This product is not available")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Cart {self.cart.id}"

class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_address = models.TextField(blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    @property
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in ["pending", "processing"]

    def cancel_order(self):
        """Cancel order and restore stock"""
        if not self.can_cancel:
            return False, "Order cannot be cancelled"

        # Restore stock for each item
        for item in self.items.all():
            item.product.adjust_stock(item.quantity, 'add')

        self.status = "cancelled"
        self.save()
        return True, "Order cancelled successfully"

    def __str__(self):
        return f"Order {self.id} by {self.user.username} ({self.status})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Price at time of purchase

    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order {self.order.id}"

class Review(models.Model):
    RATING_CHOICES = (
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent')
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=255)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Purchase verification
    is_verified_purchase = models.BooleanField(default=False)
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews'
    )
    
    # Helpfulness tracking
    helpful_votes = models.PositiveIntegerField(default=0)
    reported_count = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    moderation_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['rating']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='one_review_per_user_product'
            )
        ]
    
    def save(self, *args, **kwargs):
        # Check if this is a verified purchase
        if not self.is_verified_purchase and self.order_item:
            # Verify that the order is delivered and belongs to the reviewer
            order = self.order_item.order
            if (order.user == self.user and 
                order.status == 'delivered' and 
                self.order_item.product == self.product):
                self.is_verified_purchase = True
        
        # Update product rating
        super().save(*args, **kwargs)
        self.update_product_rating()
    
    def update_product_rating(self):
        """Update the product's average rating"""
        product = self.product
        reviews = product.reviews.filter(is_visible=True)
        if reviews.exists():
            avg_rating = reviews.aggregate(
                avg_rating=models.Avg('rating')
            )['avg_rating']
            product.average_rating = round(avg_rating, 2)
            product.total_reviews = reviews.count()
            product.save()
    
    def report(self):
        """Report inappropriate review"""
        self.reported_count += 1
        # Auto-hide if reported too many times
        if self.reported_count >= 5:
            self.is_visible = False
            self.moderation_notes += "\nAuto-hidden due to multiple reports."
        self.save()
    
    def vote_helpful(self):
        """Mark review as helpful"""
        self.helpful_votes += 1
        self.save()
    
    def __str__(self):
        return f"{self.user.username}'s review of {self.product.name}"

class ReviewImage(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='reviews/%Y/%m/%d',
        validators=[validate_image]
    )
    thumbnail = models.ImageField(
        upload_to='reviews/%Y/%m/%d/thumbnails',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.pk and self.image:  # Only on creation
            from shop.utils.image_handlers import process_product_image
            # Process image and create thumbnail
            main_image, thumbnails = process_product_image(self.image)
            # Save thumbnail
            if 'small' in thumbnails:
                self.thumbnail = thumbnails['small']
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Delete image files
        if self.image:
            self.image.delete()
        if self.thumbnail:
            self.thumbnail.delete()
        super().delete(*args, **kwargs)


class WishlistItem(models.Model):
    """
    Model for storing user wishlist items.
    
    Each item represents a product that a user has saved to their wishlist.
    The combination of user and product must be unique.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlists'
    )
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="User's notes about this wishlist item")
    
    class Meta:
        ordering = ['-added_at']
        unique_together = ['user', 'product']
        indexes = [
            models.Index(fields=['user', 'product']),
            models.Index(fields=['added_at']),
        ]
        verbose_name = 'wishlist item'
        verbose_name_plural = 'wishlist items'
    
    def __str__(self):
        return f"{self.user.username}'s wishlist item: {self.product.name}"
    
    
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_images'
    )
    image = models.ImageField(
        upload_to='products/%Y/%m/%d',
        validators=[validate_image]
    )
    thumbnail = models.ImageField(
        upload_to='products/%Y/%m/%d/thumbnails',
        blank=True,
        null=True
    )
    is_primary = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', '-is_primary']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
        ]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.pk and self.image:  # Only on creation
            from shop.utils.image_handlers import process_product_image
            main_image, thumbnails = process_product_image(self.image)
            if 'small' in thumbnails:
                self.thumbnail = thumbnails['small']
            
            # Ensure only one primary image per product
            if self.is_primary:
                self.product.product_images.filter(is_primary=True).update(is_primary=False)
        
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete()
        if self.thumbnail:
            self.thumbnail.delete()
        super().delete(*args, **kwargs)
        
class StockMovement(models.Model):
    MOVEMENT_TYPES = (
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Stock Adjustment'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    quantity = models.IntegerField(
        help_text='Positive for stock in, negative for stock out'
    )
    type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
        ]

    def __str__(self):
        return f"{self.type} - {self.quantity} units of {self.product.name}"

    def save(self, *args, **kwargs):
        # Update product stock
        if self.type == 'in':
            self.product.stock += self.quantity
        elif self.type == 'out':
            self.product.stock -= abs(self.quantity)
        elif self.type == 'adjustment':
            self.product.stock += self.quantity
        
        self.product.last_stock_update = timezone.now()
        self.product.save()
        
        super().save(*args, **kwargs)
        
class Address(models.Model):
    ADDRESS_TYPES = (
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    full_name = models.CharField(max_length=255)
    street_address = models.CharField(max_length=255)
    apartment = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', '-id']
        verbose_name_plural = 'Addresses'
        indexes = [
            models.Index(fields=['user', 'type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'type', 'is_default'],
                name='unique_default_address_per_type'
            )
        ]

    def __str__(self):
        return f"{self.user.username}'s {self.type} address"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses of same type to non-default
            Address.objects.filter(
                user=self.user,
                type=self.type,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)