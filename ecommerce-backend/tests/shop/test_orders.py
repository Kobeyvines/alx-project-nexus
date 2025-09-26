# tests/shop/test_orders.py
import pytest
from django.urls import reverse
from rest_framework import status
from shop.models import Order

@pytest.mark.django_db
class TestOrders:
    def test_order_list(self, auth_client, order):
        url = reverse("orders-list")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        # Instead of hardcoding, check the number of orders for the test user
        expected_count = Order.objects.filter(user=order.user).count()
        assert len(response.data['results']) == expected_count
        
    def test_order_detail(self, auth_client, order):
        url = reverse("orders-detail", kwargs={"pk": order.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == order.id
