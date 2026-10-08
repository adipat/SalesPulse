from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal
from core.models import Customer, Category, Product, Order, OrderItem


class Command(BaseCommand):
    help = "Seeds database with realistic e-commerce data and superuser"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # 1. Create superuser if not exists
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@ecommerce.local", "admin123")
            self.stdout.write(self.style.SUCCESS("Created superuser: admin / admin123"))
        else:
            self.stdout.write("Superuser 'admin' already exists.")

        # 2. Categories
        categories_data = [
            "Electronics",
            "Computer Accessories",
            "Home & Living",
            "Fitness & Sports",
            "Fashion & Apparel",
        ]
        category_objs = {}
        for cat_name in categories_data:
            cat, _ = Category.objects.get_or_create(name=cat_name)
            category_objs[cat_name] = cat

        # 3. Products: (name, category_name, price, cost_price, stock)
        products_data = [
            ("Dell XPS 13 Laptop", "Electronics", Decimal("75000.00"), Decimal("64000.00"), 12),
            ("Sony WH-1000XM5 Headphones", "Electronics", Decimal("24999.00"), Decimal("19500.00"), 18),
            ("Apple iPad 10th Gen", "Electronics", Decimal("38900.00"), Decimal("32000.00"), 15),
            ("Logitech MX Master 3S Mouse", "Computer Accessories", Decimal("8995.00"), Decimal("6500.00"), 35),
            ("Keychron K2 Mechanical Keyboard", "Computer Accessories", Decimal("7499.00"), Decimal("5200.00"), 24),
            ("USB-C 7-in-1 Hub", "Computer Accessories", Decimal("2499.00"), Decimal("1400.00"), 40),
            ("Ergonomic Mesh Chair", "Home & Living", Decimal("11500.00"), Decimal("7800.00"), 8),
            ("Smart LED Desk Lamp", "Home & Living", Decimal("1999.00"), Decimal("1100.00"), 22),
            ("Insulated Stainless Flask 1L", "Home & Living", Decimal("899.00"), Decimal("450.00"), 50),
            ("Anti-Skid Pro Yoga Mat", "Fitness & Sports", Decimal("1299.00"), Decimal("700.00"), 30),
            ("Adjustable Dumbbell Set (20kg)", "Fitness & Sports", Decimal("4999.00"), Decimal("3300.00"), 14),
            ("Resistance Bands Kit", "Fitness & Sports", Decimal("799.00"), Decimal("350.00"), 45),
            ("Classic Cotton Crewneck T-Shirt", "Fashion & Apparel", Decimal("699.00"), Decimal("320.00"), 60),
            ("Slim-Fit Stretch Denim Jeans", "Fashion & Apparel", Decimal("1899.00"), Decimal("950.00"), 28),
            ("Lightweight Waterproof Windcheater", "Fashion & Apparel", Decimal("2499.00"), Decimal("1300.00"), 19),
        ]

        product_objs = []
        for name, cat_name, price, cost_price, stock in products_data:
            prod, _ = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category_objs[cat_name],
                    "price": price,
                    "cost_price": cost_price,
                    "stock": stock,
                }
            )
            product_objs.append(prod)

        # 4. Customers: (name, email, phone, city, state)
        customers_data = [
            ("Rahul Sharma", "rahul.sharma@example.com", "9820112233", "Mumbai", "Maharashtra"),
            ("Priya Patel", "priya.patel@example.com", "9879114455", "Ahmedabad", "Gujarat"),
            ("Amit Verma", "amit.verma@example.com", "9845116677", "Bengaluru", "Karnataka"),
            ("Sneha Kulkarni", "sneha.k@example.com", "9822118899", "Pune", "Maharashtra"),
            ("Rohan Gupta", "rohan.g@example.com", "9811110011", "Delhi", "Delhi"),
            ("Ananya Reddy", "ananya.r@example.com", "9849112244", "Hyderabad", "Telangana"),
            ("Vikram Singh", "vikram.s@example.com", "9829113355", "Jaipur", "Rajasthan"),
            ("Pooja Nair", "pooja.nair@example.com", "9847115566", "Kochi", "Kerala"),
            ("Kavita Iyer", "kavita.i@example.com", "9840117788", "Chennai", "Tamil Nadu"),
            ("Aditya Mishra", "aditya.m@example.com", "9830119900", "Kolkata", "West Bengal"),
        ]

        customer_objs = []
        for name, email, phone, city, state in customers_data:
            cust, _ = Customer.objects.get_or_create(
                email=email,
                defaults={
                    "name": name,
                    "phone": phone,
                    "city": city,
                    "state": state,
                }
            )
            customer_objs.append(cust)

        # 5. Orders and OrderItems across the last 180 days
        statuses = ["Delivered", "Delivered", "Delivered", "Delivered", "Shipped", "Processing", "Pending", "Cancelled"]
        payment_methods = ["UPI", "UPI", "Credit Card", "Debit Card", "Cash on Delivery", "Net Banking"]

        if Order.objects.count() < 15:
            now = timezone.now()
            # Distribute 30 realistic orders across past 6 months
            for i in range(32):
                customer = random.choice(customer_objs)
                days_ago = random.randint(1, 150)
                order_time = now - timedelta(days=days_ago, hours=random.randint(1, 12))
                status = random.choice(statuses)
                pay_method = random.choice(payment_methods)

                order = Order.objects.create(
                    customer=customer,
                    order_date=order_time,
                    status=status,
                    payment_method=pay_method,
                    shipping_city=customer.city,
                    shipping_state=customer.state,
                )

                # Add 1 to 3 items per order
                items_count = random.randint(1, 3)
                selected_products = random.sample(product_objs, items_count)
                for prod in selected_products:
                    qty = random.randint(1, 2)
                    OrderItem.objects.create(
                        order=order,
                        product=prod,
                        quantity=qty,
                        selling_price=prod.price,
                    )
                order.update_total()

            self.stdout.write(self.style.SUCCESS(f"Created {Order.objects.count()} orders with items."))

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
