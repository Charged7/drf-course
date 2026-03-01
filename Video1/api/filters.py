import django_filters
from django.db.models import Sum, F
from rest_framework import filters

from api.models import Product, Order
from django import forms

STOCK_CHOICES = [
    ('', 'Всі товари'),
    ('true', 'В наявності'),
    ('false', 'Немає в наявності'),
]


class ProductFilter(django_filters.FilterSet):
    in_stock = django_filters.BooleanFilter(
        field_name='stock',
        lookup_expr='gt',
        label='В наявності',
        method='filter_in_stock',
        widget=forms.Select(choices=STOCK_CHOICES)
    )

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset

    ordering = django_filters.OrderingFilter(
        fields=(
            ('name', 'name'),
            ('price', 'price'),
            ('stock', 'stock'),
        )
    )

    class Meta:
        model = Product
        fields = {
            'name': ['iexact', 'icontains'],
            'price': ['exact', 'gte', 'lte', 'range'],
        }


class OrderFilter(django_filters.FilterSet):
    created_at_range  = django_filters.DateFromToRangeFilter(
        field_name='created_at__date',
        label='Дата створення'
    )

    user = django_filters.NumberFilter(
        field_name='user__id',
        label='ID юзера'
    )

    min_total = django_filters.NumberFilter(
        method='filter_min_total',
        label='Мінімальна сума'
    )

    def filter_min_total(self, queryset, name, value):
        return queryset.annotate(
            total=Sum(F('items__quantity') * F('items__product__price'))
        ).filter(total__gte=value)

    class Meta:
        model = Order
        fields = {
            'status': ['exact'],
        }