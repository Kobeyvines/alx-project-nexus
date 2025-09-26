# tests/shop/test_auth.py
import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
class TestAuthentication:
    def test_user_registration(self, api_client):
        url = reverse("auth_register")
        data = {"username": "newuser", "password": "password", "email": "new@user.com"}
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_user_login(self, api_client, test_user):
        url = reverse("token_obtain_pair")
        data = {"username": "testuser", "password": "password"}
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_user_logout(self, auth_client):
        url = reverse('auth_logout')
        response = auth_client.post(url, {'refresh': 'dummytoken'}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
