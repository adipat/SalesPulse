from django.contrib import admin
from .models import Customer, Category, Product, Order, OrderItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'phone', 'city', 'state', 'registration_date')
    search_fields = ('name', 'email', 'phone', 'city')
    list_filter = ('state', 'registration_date')
    ordering = ('-registration_date',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'cost_price', 'stock', 'stock_status')
    list_filter = ('category', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ('product', 'quantity', 'selling_price', 'subtotal')
    readonly_fields = ('subtotal',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order_date', 'status', 'payment_method', 'total_amount')
    list_filter = ('status', 'payment_method', 'order_date')
    search_fields = ('customer__name', 'customer__email', 'id')
    inlines = [OrderItemInline]
    ordering = ('-order_date',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'selling_price', 'subtotal')
    list_filter = ('product__category',)
    search_fields = ('order__id', 'product__name')
