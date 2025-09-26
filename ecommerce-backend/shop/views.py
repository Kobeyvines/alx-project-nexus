# Django imports
from django.contrib.auth.models import User
from django.db.models import F, Count
from django.shortcuts import get_object_or_404

# Rest framework imports
from rest_framework import viewsets, generics, permissions, status, filters as drf_filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import (
    AllowAny, IsAuthenticated, IsAdminUser, IsAuthenticatedOrReadOnly
)
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

# Third-party imports
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, NumberFilter, BooleanFilter, CharFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Local imports
from .models import (
    Product, Category, Review, Cart, CartItem, Order, OrderItem,
    Profile, ReviewImage, WishlistItem
)
from .serializers import (
    ProductSerializer, CategorySerializer, ProductListSerializer,
    ReviewSerializer, CartSerializer, CartItemSerializer,
    OrderSerializer, ProfileSerializer, RegisterSerializer,
    LogoutSerializer, UserSerializer, ProductImageSerializer,
    AddCartItemSerializer, ReviewImageSerializer, ProductReviewSerializer,
    WishlistItemSerializer
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly


# Pagination
class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination settings"""
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# Filters
class ProductFilter(FilterSet):
    """Filter for products"""
    min_price = NumberFilter(field_name="price", lookup_expr='gte')
    max_price = NumberFilter(field_name="price", lookup_expr='lte')
    is_available = BooleanFilter()
    category = CharFilter(field_name="category__slug")
    min_rating = NumberFilter(field_name="average_rating", lookup_expr='gte')

    class Meta:
        model = Product
        fields = ["min_price", "max_price", "is_available", "category", "min_rating"]


class ReviewFilter(FilterSet):
    """Filter for reviews"""
    rating = NumberFilter()
    min_rating = NumberFilter(field_name="rating", lookup_expr='gte')
    is_verified_purchase = BooleanFilter()
    has_images = BooleanFilter(method='filter_has_images')
    is_visible = BooleanFilter()

    class Meta:
        model = Review
        fields = ["rating", "min_rating", "is_verified_purchase", "has_images", "is_visible"]
        
    def filter_has_images(self, queryset, name, value):
        """Filter reviews based on whether they have images or not"""
        if value:
            return queryset.annotate(image_count=Count('images')).filter(image_count__gt=0)
        return queryset.annotate(image_count=Count('images')).filter(image_count=0)


# Authentication views
class RegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            "message": "User registered successfully",
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LogoutView(generics.GenericAPIView):
    """
    API view for user logout.
    """
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)


class UserProfileView(RetrieveAPIView):
    """
    API view for retrieving and updating user profile.
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.profile


# Product views
class ProductViewSet(ModelViewSet):
    """
    ViewSet for managing product operations.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    filterset_class = ProductFilter
    lookup_field = 'slug'
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.all()
        if self.action == 'list':
            return queryset.select_related('category')
        return queryset

    @action(detail=True, methods=['post'])
    def upload_image(self, request, slug=None):
        """Upload product images"""
        product = self.get_object()
        serializer = ProductImageSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryViewSet(ModelViewSet):
    """
    ViewSet for managing product categories.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Category.objects.prefetch_related('products')


class ReviewViewSet(ModelViewSet):
    """
    ViewSet for managing product reviews.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_class = ReviewFilter
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Review.objects.filter(product__slug=self.kwargs['product_slug'])

    def perform_create(self, serializer):
        product = get_object_or_404(Product, slug=self.kwargs['product_slug'])
        serializer.save(user=self.request.user, product=product)


# Cart and Order views
class CartViewSet(ModelViewSet):
    """
    ViewSet for managing shopping cart operations.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return Cart.objects.none()
        if not user.is_authenticated:
            return Cart.objects.none()
        return Cart.objects.filter(user=user)



    def get_object(self):
        return get_object_or_404(Cart, user=self.request.user)

    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout(self, request, pk=None):
        """
        Creates an order from the user's cart.
        """
        cart = self.get_object()
        if not cart.items.exists():
            return Response({"error": "Cannot create an order from an empty cart."}, status=status.HTTP_400_BAD_REQUEST)

        order_serializer = OrderSerializer(data=request.data, context={'request': request})
        order_serializer.is_valid(raise_exception=True)
        order = order_serializer.save(user=request.user)

        # Clear the cart
        cart.items.all().delete()

        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class CartItemViewSet(ModelViewSet):
    """
    ViewSet for managing cart items.
    """
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return CartItem.objects.none()
        if not user.is_authenticated:
            return CartItem.objects.none()
        return CartItem.objects.filter(cart__user=user)
    
    def perform_create(self, serializer):
        cart = get_object_or_404(Cart, user=self.request.user)
        serializer.save(cart=cart)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()
        if not user.is_authenticated:
            return Order.objects.none()
        return Order.objects.filter(user=user)


    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        cart = get_object_or_404(Cart, user=self.request.user)
        if not cart.items.exists():
            raise ValidationError("Cannot create order with empty cart")
        
        order = serializer.save(
            user=self.request.user,
            total_amount=cart.total_amount
        )
        
        # Create order items from cart items
        order_items = []
        for cart_item in cart.items.all():
            order_item = OrderItem(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=cart_item.product.price
            )
            order_items.append(order_item)
        
        OrderItem.objects.bulk_create(order_items)
        
        # Clear the cart
        cart.items.all().delete()
        
        return order


# Extended Product views
class ProductViewSet(ModelViewSet):
    """
    ViewSet for managing product operations.
    
    This ViewSet provides CRUD operations for products as well as additional actions
    for managing product reviews and images.
    """
    queryset = Product.objects.select_related("category").prefetch_related("reviews").all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAdminOrReadOnly]
    filterset_class = ProductFilter
    pagination_class = StandardResultsSetPagination
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created", "updated", "average_rating"]
    ordering = ["-created"]  # default ordering

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.select_related('category')
        return queryset

    @action(detail=True, methods=['post'])
    def upload_image(self, request, slug=None):
        """Upload product images"""
        product = self.get_object()
        serializer = ProductImageSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def reviews(self, request, slug=None):
        """Get reviews for this product with detailed statistics"""
        product = self.get_object()
        reviews = product.reviews.filter(is_visible=True)
        
        # Get rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            rating_distribution[i] = reviews.filter(rating=i).count()
        
        # Get verified vs unverified counts
        verified_count = reviews.filter(is_verified_purchase=True).count()
        total_count = reviews.count()
        
        # Paginate reviews
        page = self.paginate_queryset(reviews)
        serializer = ProductReviewSerializer(page or reviews, many=True)
        response = self.get_paginated_response(serializer.data) if page else Response(serializer.data)
        
        # Add summary data
        response_data = response.data.copy()
        response_data.update({
            'summary': {
                'average_rating': product.average_rating,
                'total_reviews': product.total_reviews,
                'rating_distribution': rating_distribution,
                'verified_reviews': verified_count,
                'total_reviews_shown': total_count
            }
        })
        response.data = response_data
        
        return response
    
    @swagger_auto_schema(manual_parameters=[
        openapi.Parameter('min_price', openapi.IN_QUERY, description="Minimum price", type=openapi.TYPE_NUMBER),
        openapi.Parameter('max_price', openapi.IN_QUERY, description="Maximum price", type=openapi.TYPE_NUMBER),
        openapi.Parameter('in_stock', openapi.IN_QUERY, description="In stock", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('category', openapi.IN_QUERY, description="Category slug", type=openapi.TYPE_STRING),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ReviewViewSet(ModelViewSet):
    """
    ViewSet for managing product reviews.
    
    Provides CRUD operations for reviews as well as additional actions for
    marking reviews as helpful and reporting inappropriate reviews.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_class = ReviewFilter
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, drf_filters.OrderingFilter]
    ordering_fields = ["created", "rating", "helpful_votes"]
    ordering = ["-created"]

    def get_queryset(self):
        """Filter reviews based on visibility and user"""
        queryset = Review.objects.select_related("user", "product").prefetch_related("images")
        
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return queryset.none()
        
        # Staff can see all reviews
        if self.request.user.is_staff:
            return queryset
            
        # Users can see all visible reviews and their own hidden reviews
        return queryset.filter(is_visible=True) | queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a review for a product with purchase verification"""
        product = serializer.validated_data["product"]
        
        # Check if user has already reviewed this product
        if Review.objects.filter(user=self.request.user, product=product).exists():
            raise ValidationError("You have already reviewed this product")
            
        # Check if product was purchased (for verified purchase badge)
        is_verified = OrderItem.objects.filter(
            order__user=self.request.user,
            order__status="delivered",
            product=product
        ).exists()
            
        serializer.save(
            user=self.request.user,
            is_verified_purchase=is_verified
        )

    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """Mark a review as helpful"""
        review = self.get_object()
        review.helpful_votes = F('helpful_votes') + 1
        review.save()
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Report an inappropriate review"""
        review = self.get_object()
        review.reports = F('reports') + 1
        
        # Auto-hide review if it gets too many reports
        if review.reports >= 5:  # Threshold can be adjusted
            review.is_visible = False
        
        review.save()
        return Response({'status': 'success'})


class WishlistViewSet(ModelViewSet):
    """
    ViewSet for managing user wishlists.
    
    Provides endpoints for users to manage their wishlist items:
    - List all items in wishlist
    - Add items to wishlist
    - Remove items from wishlist
    - Check if an item is in wishlist
    """
    serializer_class = WishlistItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return WishlistItem.objects.none()
        if not user.is_authenticated:
            return WishlistItem.objects.none()
        return WishlistItem.objects.filter(user=user)

    def perform_create(self, serializer):
        """Create a new wishlist item"""
        # Check if item already exists in wishlist
        product = serializer.validated_data['product']
        if WishlistItem.objects.filter(user=self.request.user, product=product).exists():
            raise ValidationError("This item is already in your wishlist")
        
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def check_product(self, request):
        """Check if a product is in the user's wishlist"""
        product_id = request.query_params.get('product_id')
        if not product_id:
            raise ValidationError("Product ID is required")
            
        exists = WishlistItem.objects.filter(
            user=request.user,
            product_id=product_id
        ).exists()
        
        return Response({'in_wishlist': exists})

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle a product in/out of the wishlist"""
        product_id = request.data.get('product_id')
        if not product_id:
            raise ValidationError("Product ID is required")
            
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise ValidationError("Invalid product ID")
            
        wishlist_item = WishlistItem.objects.filter(
            user=request.user,
            product=product
        ).first()
        
        if wishlist_item:
            wishlist_item.delete()
            return Response({
                'status': 'removed',
                'message': 'Product removed from wishlist'
            })
        else:
            WishlistItem.objects.create(user=request.user, product=product)
            return Response({
                'status': 'added',
                'message': 'Product added to wishlist'
            }, status=status.HTTP_201_CREATED)




        if order.user != request.user:
            return Response(
                {"error": "You cannot cancel an order that isn’t yours."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Idempotent: if already canceled, just return it
        if order.status == "canceled":
            serializer = self.get_serializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Otherwise cancel it
        order.status = "canceled"
        order.save()
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users by admin
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        """
        Optionally restricts the returned users by filtering against
        a `username` query parameter in the URL.
        """
        queryset = User.objects.all().order_by('-date_joined')
        username = self.request.query_params.get('username', None)
        if username is not None:
            queryset = queryset.filter(username__icontains=username)
        return queryset
    
    def perform_create(self, serializer):
        """
        Create a new user with optional profile
        """
        user = serializer.save()
        # Additional admin-specific logic can be added here
        
    def perform_update(self, serializer):
        """
        Update a user and their profile
        """
        user = serializer.save()
        # Additional admin-specific update logic can be added here