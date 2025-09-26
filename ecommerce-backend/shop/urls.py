from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    CategoryViewSet,
    ProductViewSet,
    RegisterView,
    LogoutView,
    UserProfileView,
    AdminUserViewSet,
    OrderViewSet,
    CartViewSet,
    CartItemViewSet,   # <-- separate viewset for items
    ReviewViewSet,
    WishlistViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)
router.register(r"users", AdminUserViewSet, basename="users")
router.register(r"wishlist", WishlistViewSet, basename="wishlist")
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"cart-items", CartItemViewSet, basename="cart_items")
router.register(r"reviews", ReviewViewSet, basename="reviews") 

# Nested routes are handled through actions in ProductViewSet

urlpatterns = [
    path("users/me/", UserProfileView.as_view(), name="user-profile"),
    path("", include(router.urls)),
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
]
