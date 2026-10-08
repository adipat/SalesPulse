import io
import pandas as pd
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
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

    error_msg = None
    not_registered = False
    entered_username = ''

    if request.method == 'POST':
        entered_username = request.POST.get('username', '').strip()
        entered_password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        if not entered_username or not entered_password:
            error_msg = "Please provide both username and password."
        else:
            # Check if user exists by username or email
            user_exists = (
                User.objects.filter(username__iexact=entered_username).first() or
                User.objects.filter(email__iexact=entered_username).first()
            )

            if not user_exists:
                not_registered = True
                error_msg = f"No account found for '{entered_username}'. You don't have an account yet — please register below."
            else:
                user = authenticate(request, username=user_exists.username, password=entered_password)
                if user is not None:
                    if user.is_active:
                        login(request, user)
                        if not remember_me:
                            request.session.set_expiry(0)  # Browser closes -> session ends
                        else:
                            request.session.set_expiry(1209600)  # 2 weeks
                        messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                        next_url = request.GET.get('next', 'core:dashboard')
                        return redirect(next_url)
                    else:
                        error_msg = "This account is currently disabled. Please contact the administrator."
                else:
                    error_msg = f"Incorrect password for '{user_exists.username}'. Please verify and try again."

    return render(request, 'core/auth/login.html', {
        'error_msg': error_msg,
        'not_registered': not_registered,
        'entered_username': entered_username,
    })


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
                # Read CSV via Pandas DataFrame (with resilient error recovery for internet datasets)
                df = pd.read_csv(uploaded_file, on_bad_lines='skip')

                # Smart Column Normalization for Kaggle, Superstore, & custom datasets
                col_rename = {}
                for col in df.columns:
                    clean_col = str(col).strip().lower().replace('_', ' ').replace('-', ' ')
                    if clean_col in ['customer name', 'customer', 'client name', 'client']:
                        col_rename[col] = 'customer_name'
                    elif clean_col in ['product name', 'product', 'item name', 'item']:
                        col_rename[col] = 'product_name'
                    elif clean_col in ['category', 'product category', 'dept', 'department']:
                        col_rename[col] = 'category'
                    elif clean_col in ['sales', 'amount', 'selling price', 'price', 'unit price', 'total']:
                        col_rename[col] = 'selling_price'
                    elif clean_col in ['quantity', 'qty', 'units', 'count']:
                        col_rename[col] = 'quantity'
                    elif clean_col in ['city', 'shipping city']:
                        col_rename[col] = 'city'
                    elif clean_col in ['state', 'shipping state', 'province', 'region']:
                        col_rename[col] = 'state'
                    elif clean_col in ['email', 'customer email']:
                        col_rename[col] = 'email'
                    elif clean_col in ['phone', 'contact', 'mobile', 'phone number']:
                        col_rename[col] = 'phone'
                    elif clean_col in ['payment method', 'payment mode', 'ship mode', 'payment']:
                        col_rename[col] = 'payment_method'
                    elif clean_col in ['status', 'order status']:
                        col_rename[col] = 'status'

                df = df.rename(columns=col_rename)

                # Essential fields validation
                essential_cols = ['customer_name', 'product_name', 'selling_price']
                missing_cols = [col for col in essential_cols if col not in df.columns]

                if missing_cols:
                    messages.error(request, f"Could not detect essential columns! Missing: {', '.join(missing_cols)}. Please check your CSV header.")
                else:
                    import re
                    # Clean essential fields
                    df = df.dropna(subset=['customer_name', 'product_name'])
                    df['quantity'] = pd.to_numeric(df.get('quantity', 1), errors='coerce').fillna(1).astype(int)
                    df['selling_price'] = pd.to_numeric(df['selling_price'], errors='coerce').fillna(0.0)

                    total_rows = len(df)
                    imported = 0
                    skipped = 0
                    errors = []

                    with transaction.atomic():
                        for index, row in df.iterrows():
                            try:
                                c_name = str(row['customer_name']).strip()
                                # Email synthesis if missing from external dataset
                                if 'email' in df.columns and pd.notna(row['email']) and str(row['email']).strip():
                                    c_email = str(row['email']).strip().lower()
                                else:
                                    clean_prefix = re.sub(r'[^a-zA-Z0-9]', '.', c_name).strip('.').lower()
                                    c_email = f"{clean_prefix or 'customer'}@example.com"

                                c_phone = str(row.get('phone', '9800000000')).strip()
                                if not c_phone or c_phone == 'nan':
                                    c_phone = '9800000000'

                                c_city = str(row.get('city', 'Mumbai')).strip()
                                if not c_city or c_city == 'nan':
                                    c_city = 'Mumbai'

                                c_state = str(row.get('state', 'Maharashtra')).strip()
                                if not c_state or c_state == 'nan':
                                    c_state = 'Maharashtra'

                                # 1. Customer
                                customer, _ = Customer.objects.get_or_create(
                                    email=c_email,
                                    defaults={
                                        'name': c_name,
                                        'phone': c_phone,
                                        'city': c_city,
                                        'state': c_state,
                                    }
                                )

                                # 2. Category
                                cat_name = str(row.get('category', 'General')).strip()
                                if not cat_name or cat_name == 'nan':
                                    cat_name = 'General'
                                category, _ = Category.objects.get_or_create(name=cat_name)

                                # 3. Product
                                price_val = Decimal(str(max(1.0, float(row['selling_price']))))
                                cost_val = price_val * Decimal('0.70')
                                prod_name = str(row['product_name']).strip()
                                product, _ = Product.objects.get_or_create(
                                    name=prod_name,
                                    defaults={
                                        'category': category,
                                        'price': price_val,
                                        'cost_price': cost_val,
                                        'stock': 100,
                                    }
                                )

                                # 4. Order status & payment mapping
                                status_raw = str(row.get('status', 'Delivered')).strip()
                                status = 'Delivered' if status_raw.lower() not in ['pending', 'processing', 'shipped', 'delivered', 'cancelled'] else status_raw.capitalize()

                                pay_lower = str(row.get('payment_method', 'UPI')).strip().lower()
                                if 'cod' in pay_lower or 'cash' in pay_lower:
                                    pay_method = 'Cash on Delivery'
                                elif 'debit' in pay_lower:
                                    pay_method = 'Debit Card'
                                elif 'card' in pay_lower or 'credit' in pay_lower:
                                    pay_method = 'Credit Card'
                                elif 'bank' in pay_lower or 'net' in pay_lower:
                                    pay_method = 'Net Banking'
                                else:
                                    pay_method = 'UPI'

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
                                    quantity=max(1, int(row.get('quantity', 1))),
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
                        'errors': errors[:5]
                    }
                    messages.success(request, f"Import process completed: {imported} orders imported successfully.")
            except Exception as e:
                messages.error(request, f"Failed to process CSV file: {str(e)}")
    else:
        form = CSVUploadForm()

    return render(request, 'core/import_csv.html', {'form': form, 'summary': summary})


@login_required
def download_sample_csv(request):
    """Download sample CSV file for testing bulk ingestion."""
    from pathlib import Path
    from django.conf import settings
    from django.http import FileResponse, HttpResponse

    sample_candidates = [
        Path(settings.BASE_DIR).parent / 'sample_sales_data.csv',
        Path(settings.BASE_DIR) / 'sample_sales_data.csv',
    ]
    for p in sample_candidates:
        if p.exists():
            return FileResponse(open(p, 'rb'), as_attachment=True, filename='sample_sales_data.csv')

    # Fallback template
    sample_content = (
        "customer_name,email,phone,city,state,product_name,category,quantity,selling_price,payment_method,status\n"
        "Kunal Mehra,kunal.m@example.com,9820011122,Mumbai,Maharashtra,Dell XPS 13 Laptop,Electronics,1,75000.00,Credit Card,Delivered\n"
        "Meera Nambiar,meera.n@example.com,9840022233,Chennai,Tamil Nadu,Sony WH-1000XM5 Headphones,Electronics,1,24999.00,UPI,Delivered\n"
        "Siddharth Rao,sid.rao@example.com,9880033344,Bengaluru,Karnataka,USB-C 7-in-1 Hub,Computer Accessories,3,2499.00,UPI,Delivered\n"
    )
    response = HttpResponse(sample_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_sales_data.csv"'
    return response


@login_required
def download_superstore_csv(request):
    """Download 100-row real Superstore dataset fetched from the web."""
    from pathlib import Path
    from django.conf import settings
    from django.http import FileResponse, Http404

    candidates = [
        Path(settings.BASE_DIR) / 'superstore_dataset_test.csv',
        Path(settings.BASE_DIR).parent / 'superstore_dataset_test.csv',
    ]
    for target in candidates:
        if target.exists():
            return FileResponse(open(target, 'rb'), as_attachment=True, filename='superstore_dataset_test.csv')
    raise Http404("Superstore dataset not found.")


@login_required
def download_india_csv(request):
    """Download 149-row Indian E-Commerce dataset from GitHub."""
    from pathlib import Path
    from django.conf import settings
    from django.http import FileResponse, Http404

    candidates = [
        Path(settings.BASE_DIR) / 'ecommerce_india_online_test.csv',
        Path(settings.BASE_DIR).parent / 'ecommerce_india_online_test.csv',
    ]
    for target in candidates:
        if target.exists():
            return FileResponse(open(target, 'rb'), as_attachment=True, filename='ecommerce_india_online_test.csv')
    raise Http404("Indian e-commerce dataset not found.")



