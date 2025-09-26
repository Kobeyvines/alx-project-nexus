from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Ecommerce API",
        default_version="v1",
        description="API documentation for the ecommerce backend",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url="https://ecommerce-backend-bxd7.onrender.com",  # 👈 only domain, no /api
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('shop.urls')),  

    # Swagger & Redoc under /api/
    path('api/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Redirect root → swagger
    path("", RedirectView.as_view(url="/api/swagger/", permanent=False)),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)