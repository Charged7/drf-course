import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.factories import UserFactory, OrderFactory, ProductFactory, AdminFactory
from api.serializers import OrderCreateSerializer


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_user_gets_only_his_orders(api_client):
    normal_user = UserFactory()
    OrderFactory.create_batch(2, user=normal_user)  # створює 2 замовлення
    OrderFactory.create_batch(2)  # чужі замовлення

    api_client.force_authenticate(user=normal_user)
    response = api_client.get(reverse('order-list'))

    assert response.status_code == status.HTTP_200_OK
    assert all(order['user'] == normal_user.id for order in response.json())


@pytest.mark.django_db
def test_admin_user_gets_all_orders(api_client):
    admin = AdminFactory(is_staff=True, is_superuser=True)
    user1 = UserFactory()
    user2 = UserFactory()

    OrderFactory.create_batch(2, user=user1)  # 2 замовлення user1
    OrderFactory.create_batch(2, user=user2)  # 2 замовлення user2
    OrderFactory.create_batch(1, user=admin)  # 1 замовлення admin

    api_client.force_authenticate(user=admin)
    response = api_client.get(reverse('order-list'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 5


@pytest.mark.django_db
def test_not_authenticated_user_gets_error(api_client):
    response = api_client.get(reverse('order-list'))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_product_list(api_client):
    ProductFactory.create_batch(3)
    response = api_client.get(reverse('product-list'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 3


@pytest.mark.django_db
def test_product_detail(api_client):
    product = ProductFactory()
    response = api_client.get(reverse('product-detail', kwargs={'product_id': product.pk}))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['name'] == product.name
    assert float(response.json()['price']) == float(product.price)


@pytest.mark.django_db
@pytest.mark.parametrize("method, data", [
    ("put", {'name': 'Updated', 'price': 99.99, 'stock': 10}),
    ("patch", {'name': 'Updated'}),
    ("delete", None),
])
def test_unauthorized_user_cannot_modify_product(api_client, method, data):
    product = ProductFactory()
    url = reverse('product-detail', kwargs={'product_id': product.pk})

    response = getattr(api_client, method)(url, data=data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_authorized_user_can_update_product(api_client):
    product = ProductFactory()
    admin = AdminFactory()

    api_client.force_authenticate(user=admin)

    response = api_client.put(reverse('product-detail', kwargs={'product_id': product.pk}), data={
        'name': 'Updated Name',
        'price': 99.99,
        'stock': 10
    })

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_order_create_serializer_valid_data():
    user = UserFactory()
    product = ProductFactory(stock=10)
    data = {
        'items': [{'product': product.id, 'quantity': 2}]
    }
    serializer = OrderCreateSerializer(data=data)
    assert serializer.is_valid(), serializer.errors