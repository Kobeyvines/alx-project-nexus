from django.utils.text import slugify
from django.db import transaction
from rest_framework import serializers
from .models import (
    Category, Product, Profile, Cart, CartItem, Order,
    Review, ReviewImage, WishlistItem, ProductImage
)
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError





class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]
        
    def validate_name(self, value):
        if Category.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = slugify(validated_data["name"])
        return super().create(validated_data)


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for product images
    """
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'thumbnail', 'alt_text', 'is_primary', 'created_at']
        read_only_fields = ['thumbnail', 'created_at']

    def validate_image(self, value):
        """
        Validate image size and dimensions
        """
        if value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("Image size cannot exceed 5MB")
        return value

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Category.objects.all()
    )

    slug = serializers.SlugField(required=False)
    images = ProductImageSerializer(many=True, read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    in_stock = serializers.ReadOnlyField() 

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "description",
            "price",
            "category",
            "stock",
            "in_stock",
            "images"
        ]

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = slugify(validated_data["name"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "slug" not in validated_data and validated_data.get("name"):
            validated_data["slug"] = slugify(validated_data["name"])
        return super().update(instance, validated_data)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email"),
            password=validated_data["password"]
        )


class LogoutSerializer(serializers.Serializer):
    """
    Serializer for user logout.
    """
    refresh = serializers.CharField()

    default_error_messages = {
        'bad_token': ('Token is expired or invalid')
    }

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except TokenError:
            self.fail('bad_token')


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Profile
        fields = ["username", "email", "phone", "address", "bio", "created_at"]
        read_only_fields = ["created_at"]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "profile"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {})
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )
        Profile.objects.update_or_create(user=user, defaults=profile_data)
        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance.username = validated_data.get("username", instance.username)
        instance.email = validated_data.get("email", instance.email)
        if "password" in validated_data:
            instance.set_password(validated_data["password"])
        instance.save()
        Profile.objects.update_or_create(user=instance, defaults=profile_data)
        return instance


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_name", "product_price", "quantity", "subtotal"]
        read_only_fields = ["id", "product_name", "product_price", "subtotal"]

    def get_subtotal(self, obj):
        return obj.product.price * obj.quantity



class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "user", "items", "total_price", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "items", "total_price", "created_at", "updated_at"]
        
    def get_total_price(self, obj):
        return obj.total_price()


class AddCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ["product", "quantity"]
        
    def create(self, validated_data):
        # cart is passed in perform_create
        return CartItem.objects.create(**validated_data)


class OrderSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "user", "created_at", "items", "status", "total_amount"]
        read_only_fields = ["id", "user", "created_at", "items", "total_amount"]


    def create(self, validated_data):
        user = self.context['request'].user
        # Check if user has a pending order and prevent creating a new one
        # to avoid creating a new order with the same items.
        if Order.objects.filter(user=user, status="pending").exists():
            raise serializers.ValidationError("You have an existing pending order.")
        
        order = Order.objects.create(user=user, total_amount=0)
        return order


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ['id', 'image', 'thumbnail', 'created_at']
        read_only_fields = ['thumbnail', 'created_at']

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    images = ReviewImageSerializer(many=True, read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())  # 👈 Fix
    product_name = serializers.CharField(source='product.name', read_only=True)
    

    class Meta:
        model = Review
        fields = [
            'id', 'product', 'product_name', 'user', 'rating', 'title', 
            'comment', 'created_at', 'updated_at', 'is_verified_purchase',
            'helpful_votes', 'images'
        ]
        read_only_fields = [
            'user', 'created_at', 'updated_at', 'is_verified_purchase',
            'helpful_votes', 'product_name'
        ]

    def create(self, validated_data):
        # The user is passed from the view, so we don't need to handle it here.
        review = Review.objects.create(**validated_data)
        return review


class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for displaying reviews in product detail"""
    user = serializers.StringRelatedField()
    images = ReviewImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'rating', 'title', 'comment',
            'created_at', 'is_verified_purchase', 'helpful_votes',
            'images'
        ]
        read_only_fields = fields


class WishlistItemSerializer(serializers.ModelSerializer):
    """
    Serializer for wishlist items.
    
    Includes basic product information along with wishlist-specific fields.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    product_image = serializers.ImageField(source='product.image', read_only=True)
    is_available = serializers.BooleanField(source='product.is_available', read_only=True)
    
    class Meta:
        model = WishlistItem
        fields = [
            'id', 'product', 'product_name', 'product_price',
            'product_image', 'is_available', 'added_at', 'notes'
        ]
        read_only_fields = ['id', 'added_at']

    def validate_product(self, value):
        """
        Validate that the product can be added to wishlist:
        - Product must exist
        - Product must be active/available
        """
        if not value.is_available:
            raise serializers.ValidationError(
                "This product is currently unavailable and cannot be added to wishlist"
            )
        return value

    def create(self, validated_data):
        """
        Create a new wishlist item, ensuring uniqueness of user-product combination.
        """
        user = self.context['request'].user
        product = validated_data.get('product')
        
        # Check if item already exists in user's wishlist
        if WishlistItem.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError(
                "This item is already in your wishlist"
            )
            
        return WishlistItem.objects.create(
            user=user,
            **validated_data
        )

class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    
    class Meta:
        model = Product 
        fields = ['id', 'name', 'slug', 'price', 'image', 'category', 'average_rating', 'total_reviews']