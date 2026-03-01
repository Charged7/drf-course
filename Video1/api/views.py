from django.db.models import Max
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from rest_framework import generics, filters, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.filters import ProductFilter, OrderFilter
from api.models import Product, Order, User
from api.pagination import ProductPagination
from api.serializers import ProductSerializer, OrderSerializer, ProductInfoSerializer, OrderCreateSerializer, \
    OrderUpdateSerializer, UserSerializer
from api.tasks import send_order_confirmation_email


@extend_schema(tags=["Товари"])
class ProductListCreateAPIView(generics.ListCreateAPIView):
    throttle_scope = 'products'
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_class = ProductFilter
    pagination_class = None

    @method_decorator(cache_page(60 * 60, key_prefix='product_list'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        keys = cache.keys('*.product_list.*')
        if keys:
            cache.delete_many(keys)

    def get_permissions(self):
        self.permission_classes = [AllowAny]
        if self.request.method == 'POST':
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()


@extend_schema(tags=["Товари"])
class ProductDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_url_kwarg = 'product_id'

    def get_permissions(self):
        self.permission_classes = [AllowAny]
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()


@extend_schema(
        summary="Статистика по товарах",
        responses={200: ProductInfoSerializer},
        tags=["Товари"],
        examples=[
            OpenApiExample(
                'Приклад статистики',
                value={
                    'products': [
                        {'id': 1, 'name': 'Ноутбук', 'price': 25000.00},
                        {'id': 2, 'name': 'Мишка', 'price': 500.00}
                    ],
                    'count': 2,
                    'max_price': 25000.00
                },
                response_only=True,  # Показувати тільки у відповіді
            )
        ]
)
class ProductInfoAPIView(APIView):
    def get(self, request):
        products = Product.objects.all()
        serializer = ProductInfoSerializer({
            'products': products,
            'count': products.count(),
            'max_price': products.aggregate(max_price=Max('price'))['max_price'],
        })
        return Response(serializer.data)


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = None


@extend_schema(tags=["Замовлення"])
class OrderViewSet(viewsets.ModelViewSet):
    throttle_scope = 'orders'
    queryset = Order.objects.prefetch_related('items__product')
    serializer_class = OrderSerializer
    permission_classes= [IsAuthenticated]
    pagination_class = None
    filterset_class = OrderFilter

    def perform_create(self, serializer):
        order = serializer.save(user=self.request.user)
        send_order_confirmation_email.delay(order.order_id, self.request.user.email)

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]
