import io
import pandas as pd
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import Customer, Category, Product, Order, OrderItem
from .forms import (
    UserRegistrationForm,
    CustomerForm,
    CategoryForm,
    ProductForm,
    OrderForm,
    OrderItemForm,
    CSVUploadForm
)
from .analytics import get_analytics_data


# -------------------------------------------------------------
# AUTHENTICATION VIEWS
# -------------------------------------------------------------
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, f"Account created for {user.username}! You can now log in.")
            return redirect('core:login')
    else:
        form = UserRegistrationForm()
    return render(request, 'core/auth/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                next_url = request.GET.get('next', 'core:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid credentials provided.")
    else:
        form = AuthenticationForm()
    return render(request, 'core/auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('core:login')


# -------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------
@login_required
def dashboard_view(request):
    analytics = get_analytics_data()
    recent_orders = Order.objects.select_related('customer').order_by('-order_date')[:6]
    low_stock_products = Product.objects.filter(stock__lte=10).order_by('stock')[:5]

    context = {
        'kpis': analytics['kpis'],
        'insights': analytics['insights'],
        'charts': analytics['charts'],
        'recent_orders': recent_orders,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'core/dashboard.html', context)


# -------------------------------------------------------------
# CUSTOMER CRUD
# -------------------------------------------------------------
@login_required
def customer_list(request):
    query = request.GET.get('q', '').strip()
    customers = Customer.objects.annotate(orders_count=Count('orders')).order_by('-registration_date')

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(city__icontains=query) |
            Q(phone__icontains=query)
        )

    context = {
        'customers': customers,
        'query': query,
    }
    return render(request, 'core/customers/list.html', context)


@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Customer '{customer.name}' added successfully.")
            return redirect('core:customer_list')
    else:
        form = CustomerForm()
    return render(request, 'core/customers/form.html', {'form': form, 'title': 'Add New Customer'})


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Customer '{customer.name}' updated successfully.")
            return redirect('core:customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'core/customers/form.html', {'form': form, 'title': f'Edit {customer.name}', 'customer': customer})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f"Customer '{name}' deleted.")
        return redirect('core:customer_list')
    return render(request, 'core/common/confirm_delete.html', {
        'object': customer,
        'type': 'Customer',
        'cancel_url': 'core:customer_list'
    })


# -------------------------------------------------------------
# CATEGORY CRUD
# -------------------------------------------------------------
@login_required
def category_list(request):
    categories = Category.objects.annotate(products_count=Count('products')).order_by('name')
    return render(request, 'core/categories/list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category '{category.name}' created.")
            return redirect('core:category_list')
    else:
        form = CategoryForm()
    return render(request, 'core/categories/form.html', {'form': form, 'title': 'Add Category'})


@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated.")
            return redirect('core:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'core/categories/form.html', {'form': form, 'title': f'Edit {category.name}'})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
        return redirect('core:category_list')
    return render(request, 'core/common/confirm_delete.html', {
        'object': category,
        'type': 'Category',
        'cancel_url': 'core:category_list'
    })


# -------------------------------------------------------------
# PRODUCT CRUD
# -------------------------------------------------------------
@login_required
def product_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    products = Product.objects.select_related('category').order_by('name')

    if query:
        products = products.filter(name__icontains=query)
    if category_id:
        products = products.filter(category_id=category_id)

    categories = Category.objects.all().order_by('name')

    context = {
        'products': products,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    }
    return render(request, 'core/products/list.html', context)


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product.name}' created.")
            return redirect('core:product_list')
    else:
        form = ProductForm()
    return render(request, 'core/products/form.html', {'form': form, 'title': 'Add Product'})


@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect('core:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'core/products/form.html', {'form': form, 'title': f'Edit {product.name}'})


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f"Product '{name}' deleted.")
        return redirect('core:product_list')
    return render(request, 'core/common/confirm_delete.html', {
        'object': product,
        'type': 'Product',
        'cancel_url': 'core:product_list'
    })


# -------------------------------------------------------------
# ORDER MANAGEMENT
# -------------------------------------------------------------
@login_required
def order_list(request):
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    orders = Order.objects.select_related('customer').order_by('-order_date')

    if status_filter:
        orders = orders.filter(status=status_filter)
    if query:
        orders = orders.filter(
            Q(customer__name__icontains=query) |
            Q(customer__email__icontains=query) |
            Q(id__icontains=query)
        )

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'statuses': [s[0] for s in Order.STATUS_CHOICES],
        'query': query,
    }
    return render(request, 'core/orders/list.html', context)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('customer'), pk=pk)
    items = order.items.select_related('product', 'product__category')
    return render(request, 'core/orders/detail.html', {'order': order, 'items': items})


@login_required
def order_create(request):
    """
    Creates an Order and associated OrderItems in one cohesive, intuitive form.
    """
    products = Product.objects.all().order_by('name')

    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('price[]')

        if order_form.is_valid():
            if not product_ids:
                messages.error(request, "Please add at least one product item to create the order.")
            else:
                with transaction.atomic():
                    order = order_form.save(commit=False)
                    order.save()

                    for pid, qty_str, price_str in zip(product_ids, quantities, prices):
                        if pid and qty_str:
                            prod = Product.objects.get(id=int(pid))
                            qty = max(1, int(qty_str))
                            selling_price = Decimal(price_str) if price_str else prod.price

                            OrderItem.objects.create(
                                order=order,
                                product=prod,
                                quantity=qty,
                                selling_price=selling_price,
                            )
                            # Update stock
                            prod.stock = max(0, prod.stock - qty)
                            prod.save(update_fields=['stock'])

                    order.update_total()
                messages.success(request, f"Order #{order.id} created successfully!")
                return redirect('core:order_detail', pk=order.id)
    else:
        order_form = OrderForm()

    return render(request, 'core/orders/create.html', {
        'order_form': order_form,
        'products': products,
    })


@login_required
def order_update_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save(update_fields=['status'])
            messages.success(request, f"Order #{order.id} status updated to {new_status}.")
        return redirect('core:order_detail', pk=order.id)
    return redirect('core:order_list')


@login_required
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        order_id = order.id
        order.delete()
        messages.success(request, f"Order #{order_id} deleted.")
        return redirect('core:order_list')
    return render(request, 'core/common/confirm_delete.html', {
        'object': order,
        'type': f'Order #{order.id}',
        'cancel_url': 'core:order_list'
    })


# -------------------------------------------------------------
# CSV IMPORT WITH PANDAS
# -------------------------------------------------------------
@login_required
def csv_import_view(request):
    summary = None

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['csv_file']
            try:
                # Read CSV via Pandas DataFrame
                df = pd.read_csv(uploaded_file)

                # Required columns validation
                required_cols = [
                    'customer_name', 'email', 'phone', 'city', 'state',
                    'product_name', 'category', 'quantity', 'selling_price',
                    'payment_method', 'status'
                ]
                missing_cols = [col for col in required_cols if col not in df.columns]

                if missing_cols:
                    messages.error(request, f"Invalid CSV format! Missing required columns: {', '.join(missing_cols)}")
                else:
                    # Clean data using Pandas
                    df = df.dropna(subset=['customer_name', 'email', 'product_name'])
                    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1).astype(int)
                    df['selling_price'] = pd.to_numeric(df['selling_price'], errors='coerce').fillna(0.0)

                    total_rows = len(df)
                    imported = 0
                    skipped = 0
                    errors = []

                    with transaction.atomic():
                        for index, row in df.iterrows():
                            try:
                                # 1. Customer
                                customer, _ = Customer.objects.get_or_create(
                                    email=str(row['email']).strip(),
                                    defaults={
                                        'name': str(row['customer_name']).strip(),
                                        'phone': str(row.get('phone', '')).strip(),
                                        'city': str(row.get('city', 'Mumbai')).strip(),
                                        'state': str(row.get('state', 'Maharashtra')).strip(),
                                    }
                                )

                                # 2. Category
                                category, _ = Category.objects.get_or_create(
                                    name=str(row.get('category', 'General')).strip()
                                )

                                # 3. Product
                                price_val = Decimal(str(row['selling_price']))
                                cost_val = price_val * Decimal('0.70')  # estimate cost if not provided
                                product, _ = Product.objects.get_or_create(
                                    name=str(row['product_name']).strip(),
                                    defaults={
                                        'category': category,
                                        'price': price_val,
                                        'cost_price': cost_val,
                                        'stock': 50,
                                    }
                                )

                                # 4. Order
                                status = str(row.get('status', 'Delivered')).strip()
                                pay_method = str(row.get('payment_method', 'UPI')).strip()

                                order = Order.objects.create(
                                    customer=customer,
                                    status=status,
                                    payment_method=pay_method,
                                    shipping_city=customer.city,
                                    shipping_state=customer.state,
                                )

                                # 5. OrderItem
                                OrderItem.objects.create(
                                    order=order,
                                    product=product,
                                    quantity=int(row['quantity']),
                                    selling_price=price_val,
                                )
                                order.update_total()
                                imported += 1
                            except Exception as e:
                                skipped += 1
                                errors.append(f"Row {index + 1}: {str(e)}")

                    summary = {
                        'total_rows': total_rows,
                        'imported': imported,
                        'skipped': skipped,
                        'errors': errors[:5]  # first 5 errors to avoid flooding
                    }
                    messages.success(request, f"Import process completed: {imported} orders imported successfully.")
            except Exception as e:
                messages.error(request, f"Failed to process CSV file: {str(e)}")
    else:
        form = CSVUploadForm()

    return render(request, 'core/import_csv.html', {'form': form, 'summary': summary})
