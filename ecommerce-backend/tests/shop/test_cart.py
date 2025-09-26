import pytest
from django.urls import reverse
from rest_framework import status
from shop.models import CartItem, Order

@pytest.mark.django_db
class TestCart:
    def test_add_to_cart(self, auth_client, product):
        url = reverse("cartitem-list")
        data = {"product": product.pk, "quantity": 1}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert CartItem.objects.count() == 1

    def test_view_cart(self, auth_client, cart_item):
        url = reverse("cart-detail", kwargs={"pk": cart_item.cart.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.data
        assert "items" in response.data
        assert len(response.data["items"]) == 1

    def test_checkout(self, auth_client, cart_item):
        url = reverse("cart-checkout", kwargs={"pk": cart_item.cart.pk})
        response = auth_client.post(url, {}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.data
        assert Order.objects.count() == 1
        assert CartItem.objects.count() == 0
