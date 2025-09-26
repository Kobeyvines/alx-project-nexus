# tests/conftest.py
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from shop.models import Category, Product, Profile, Cart, Review

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_password():
    return 'test_password123'

@pytest.fixture
def test_user(db, test_password):
    user = User.objects.create_user(username='testuser', password='password')
    Profile.objects.get_or_create(user=user)
    return user

@pytest.fixture
def admin_user(db, test_password):
    user = User.objects.create_superuser(username='admin', password='password', email='admin@example.com')
    Profile.objects.get_or_create(user=user)
    return user

@pytest.fixture
def category(db):
    return Category.objects.create(
        name='Test Category',
        slug='test-category'
    )

@pytest.fixture
def product(db, category):
    return Product.objects.create(
        category=category,
        name='Test Product',
        slug='test-product',
        price=99.99,
        stock=10
    )

@pytest.fixture
def review(db, test_user, product):
    return Review.objects.create(user=test_user, product=product, rating=4, comment="A good product")

@pytest.fixture
def cart(db, test_user):
    cart, _ = Cart.objects.get_or_create(user=test_user)
    return cart

@pytest.fixture
def cart_item(db, cart, product):
    return cart.items.create(product=product, quantity=1)


@pytest.fixture
def auth_client(api_client, test_user):
    api_client.force_authenticate(user=test_user)
    return api_client

@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def order(db, test_user):
    from shop.models import Order
    return Order.objects.create(user=test_user, total_amount=0)