# tes@pytest.mark.django_db
import pytest
from django.urls import reverse
from rest_framework import status
# ...existing imports...

@pytest.mark.django_db
class TestReviews:
    def test_create_review(self, auth_client, product):
        url = reverse('reviews-list')
        data = {
            'product': product.id,
            'rating': 5,
            'title': 'Great Product!',
            'comment': 'This is an excellent product, highly recommended.'
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_review_list_for_product(self, api_client, review):
        url = reverse("product-reviews", kwargs={"slug": review.product.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) > 0