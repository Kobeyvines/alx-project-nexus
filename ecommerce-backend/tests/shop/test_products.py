# tests/shop/test_products.py
import pytest
from django.urls import reverse
from rest_framework import status
from shop.models import Product, Category  # Assuming your Product and Category models are in shop.models

@pytest.mark.django_db
class TestProducts:
    def setup_method(self, method):
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            description="Test description",
            price=10.00,
            category=self.category,
        )

    def test_product_list(self, api_client):
        url = reverse('product-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0

    def test_product_detail(self, api_client):
        url = reverse("product-detail", kwargs={"slug": self.product.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == self.product.name

    def test_product_create(self, admin_client):
        url = reverse("product-list")
        data = {
            "name": "New Product",
            "slug": "new-product",
            "description": "A new product",
            "price": 20.00,
            "category": self.category.slug,
        }
        response = admin_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Product.objects.count() == 2