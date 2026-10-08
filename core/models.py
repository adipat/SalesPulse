from django.db import models
from django.utils import timezone
from decimal import Decimal


class Customer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    registration_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.name} ({self.email})"

    @property
    def total_orders_count(self):
        return self.orders.count()

    @property
    def total_spent(self):
        # Exclude cancelled orders from total spending calculation
        valid_orders = self.orders.exclude(status='Cancelled')
        total = sum(order.total_amount for order in valid_orders)
        return total


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current retail price")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost price per unit")
    stock = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (₹{self.price})"

    @property
    def stock_status(self):
        if self.stock <= 0:
            return "Out of Stock"
        elif self.stock < 10:
            return "Low Stock"
        return "In Stock"


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('Cash on Delivery', 'Cash on Delivery'),
        ('UPI', 'UPI'),
        ('Credit Card', 'Credit Card'),
        ('Debit Card', 'Debit Card'),
        ('Net Banking', 'Net Banking'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    order_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_CHOICES, default='Cash on Delivery')
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"Order #{self.id} - {self.customer.name} (₹{self.total_amount})"

    def update_total(self):
        """Calculate total amount from related OrderItems."""
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return total

    def save(self, *args, **kwargs):
        # Auto-fill shipping city and state from customer if not provided
        if not self.shipping_city and self.customer:
            self.shipping_city = self.customer.city
        if not self.shipping_state and self.customer:
            self.shipping_state = self.customer.state
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    # Historical selling price at the time of purchase
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.product.name} x {self.quantity} (Order #{self.order.id})"

    def save(self, *args, **kwargs):
        # If selling_price is not provided, populate with product's current price
        if self.selling_price is None and self.product:
            self.selling_price = self.product.price
        self.subtotal = Decimal(self.selling_price) * Decimal(self.quantity)
        super().save(*args, **kwargs)

    @property
    def profit(self):
        """Profit = (selling_price - product.cost_price) * quantity"""
        return (Decimal(self.selling_price) - Decimal(self.product.cost_price)) * Decimal(self.quantity)
