from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from api.models import OrderItem, Order, User, Product


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 1
    tab = True  # Відобразити інлайни у вигляді окремої вкладки (опціонально)


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    inlines = [
        OrderItemInline
    ]
    list_display = ["order_id", "user", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["order_id", "user__email"]
    list_editable = ["status"]


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    pass


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "price", "stock", "in_stock"]
    list_filter = ["stock"]
    search_fields = ["name", "price"]
