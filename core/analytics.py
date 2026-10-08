import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from decimal import Decimal
from django.db.models import Sum, Count
from .models import Order, OrderItem, Product, Category, Customer


def get_analytics_data():
    """
    Extracts e-commerce records, processes them via Pandas & NumPy,
    and returns calculated KPIs, business insights, and Plotly charts.
    """
    # 1. Query raw database records
    orders_qs = Order.objects.all().select_related('customer')
    items_qs = OrderItem.objects.all().select_related('order', 'product', 'product__category', 'order__customer')

    # Default empty response structure
    empty_result = {
        'kpis': {
            'total_revenue': 0.0,
            'total_orders': 0,
            'total_customers': Customer.objects.count(),
            'products_sold': 0,
            'aov': 0.0,
            'total_profit': 0.0,
            'repeat_customer_rate': 0.0,
        },
        'insights': {
            'top_category': 'N/A',
            'top_product': 'N/A',
            'most_profitable_category': 'N/A',
            'top_city': 'N/A',
            'repeat_revenue_pct': 0.0,
        },
        'charts': {}
    }

    if not orders_qs.exists() or not items_qs.exists():
        return empty_result

    # 2. Build Pandas DataFrames
    orders_data = []
    for o in orders_qs:
        orders_data.append({
            'order_id': o.id,
            'customer_id': o.customer.id,
            'customer_name': o.customer.name,
            'order_date': o.order_date,
            'status': o.status,
            'payment_method': o.payment_method,
            'shipping_city': o.shipping_city,
            'shipping_state': o.shipping_state,
            'total_amount': float(o.total_amount),
        })
    df_orders = pd.DataFrame(orders_data)

    items_data = []
    for it in items_qs:
        items_data.append({
            'item_id': it.id,
            'order_id': it.order.id,
            'product_id': it.product.id,
            'product_name': it.product.name,
            'category_name': it.product.category.name,
            'quantity': it.quantity,
            'selling_price': float(it.selling_price),
            'cost_price': float(it.product.cost_price),
            'subtotal': float(it.subtotal),
            'status': it.order.status,
            'order_date': it.order.order_date,
            'customer_id': it.order.customer.id,
            'city': it.order.shipping_city,
        })
    df_items = pd.DataFrame(items_data)

    # 3. Data Cleaning & Feature Engineering
    df_orders['order_date'] = pd.to_datetime(df_orders['order_date'])
    df_items['order_date'] = pd.to_datetime(df_items['order_date'])

    # Exclude Cancelled orders for financial KPIs
    df_valid_orders = df_orders[df_orders['status'] != 'Cancelled']
    df_valid_items = df_items[df_items['status'] != 'Cancelled']

    # Calculate item-level profit using NumPy vectorized arithmetic
    # profit = (selling_price - cost_price) * quantity
    df_valid_items['profit'] = (df_valid_items['selling_price'] - df_valid_items['cost_price']) * df_valid_items['quantity']

    # 4. KPI Calculations
    total_revenue = float(np.sum(df_valid_orders['total_amount'])) if not df_valid_orders.empty else 0.0
    total_orders = len(df_valid_orders)
    total_customers = Customer.objects.count()
    products_sold = int(np.sum(df_valid_items['quantity'])) if not df_valid_items.empty else 0
    aov = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0
    total_profit = float(np.sum(df_valid_items['profit'])) if not df_valid_items.empty else 0.0

    # Repeat Customer Rate
    # Customer with > 1 valid orders
    orders_per_customer = df_valid_orders.groupby('customer_id')['order_id'].count()
    repeat_customers_count = int(np.sum(orders_per_customer > 1))
    total_customers_with_orders = len(orders_per_customer)
    repeat_customer_rate = round((repeat_customers_count / total_customers_with_orders * 100), 1) if total_customers_with_orders > 0 else 0.0

    kpis = {
        'total_revenue': round(total_revenue, 2),
        'total_orders': total_orders,
        'all_orders_count': len(df_orders),
        'total_customers': total_customers,
        'products_sold': products_sold,
        'aov': aov,
        'total_profit': round(total_profit, 2),
        'repeat_customer_rate': repeat_customer_rate,
    }

    # 5. Business Insights
    insights = {}
    if not df_valid_items.empty:
        # Highest revenue category
        cat_rev = df_valid_items.groupby('category_name')['subtotal'].sum()
        insights['top_category'] = cat_rev.idxmax() if not cat_rev.empty else 'N/A'

        # Best-selling product by quantity
        prod_qty = df_valid_items.groupby('product_name')['quantity'].sum()
        insights['top_product'] = prod_qty.idxmax() if not prod_qty.empty else 'N/A'

        # Most profitable category
        cat_prof = df_valid_items.groupby('category_name')['profit'].sum()
        insights['most_profitable_category'] = cat_prof.idxmax() if not cat_prof.empty else 'N/A'

        # Top city by revenue
        city_rev = df_valid_orders.groupby('shipping_city')['total_amount'].sum()
        insights['top_city'] = city_rev.idxmax() if not city_rev.empty else 'N/A'

        # Repeat customer revenue percentage
        repeat_cust_ids = orders_per_customer[orders_per_customer > 1].index
        repeat_rev = df_valid_orders[df_valid_orders['customer_id'].isin(repeat_cust_ids)]['total_amount'].sum()
        insights['repeat_revenue_pct'] = round(float(repeat_rev / total_revenue * 100), 1) if total_revenue > 0 else 0.0
    else:
        insights = empty_result['insights']

    # 6. Chart Generation (Plotly)
    charts = {}

    # Common styling template for dashboard
    chart_layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, -apple-system, sans-serif', size=12, color='#334155'),
        margin=dict(l=30, r=30, t=40, b=30),
    )

    # Chart 1: Monthly Revenue Trend (Line Chart)
    if not df_valid_orders.empty:
        df_orders_monthly = df_valid_orders.copy()
        df_orders_monthly['year_month'] = df_orders_monthly['order_date'].dt.strftime('%Y-%m')
        monthly_rev = df_orders_monthly.groupby('year_month')['total_amount'].sum().reset_index()
        monthly_rev = monthly_rev.sort_values('year_month')

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=monthly_rev['year_month'],
            y=monthly_rev['total_amount'],
            mode='lines+markers',
            name='Revenue (₹)',
            line=dict(color='#2563eb', width=3),
            marker=dict(size=7, color='#1d4ed8')
        ))
        fig1.update_layout(
            title="Monthly Revenue Trend (₹)",
            xaxis_title="Month",
            yaxis_title="Revenue (₹)",
            **chart_layout
        )
        charts['monthly_revenue'] = fig1.to_html(full_html=False, include_plotlyjs=False)

        # Chart 2: Monthly Orders Volume (Bar Chart)
        monthly_orders = df_orders_monthly.groupby('year_month')['order_id'].count().reset_index()
        fig2 = px.bar(
            monthly_orders,
            x='year_month',
            y='order_id',
            title="Monthly Orders Volume",
            labels={'year_month': 'Month', 'order_id': 'Number of Orders'},
            color_discrete_sequence=['#3b82f6']
        )
        fig2.update_layout(**chart_layout)
        charts['monthly_orders'] = fig2.to_html(full_html=False, include_plotlyjs=False)

    # Chart 3: Revenue by Category (Bar Chart)
    if not df_valid_items.empty:
        cat_summary = df_valid_items.groupby('category_name').agg(
            revenue=('subtotal', 'sum'),
            profit=('profit', 'sum')
        ).reset_index().sort_values('revenue', ascending=False)

        fig3 = px.bar(
            cat_summary,
            x='category_name',
            y='revenue',
            title="Revenue by Category (₹)",
            labels={'category_name': 'Category', 'revenue': 'Revenue (₹)'},
            color_discrete_sequence=['#0ea5e9']
        )
        fig3.update_layout(**chart_layout)
        charts['category_revenue'] = fig3.to_html(full_html=False, include_plotlyjs=False)

        # Chart 4: Profit by Category
        fig4 = px.bar(
            cat_summary.sort_values('profit', ascending=False),
            x='category_name',
            y='profit',
            title="Profit by Category (₹)",
            labels={'category_name': 'Category', 'profit': 'Profit (₹)'},
            color_discrete_sequence=['#10b981']
        )
        fig4.update_layout(**chart_layout)
        charts['category_profit'] = fig4.to_html(full_html=False, include_plotlyjs=False)

        # Chart 5: Top 10 Products by Quantity Sold (Horizontal Bar Chart)
        top_prods = df_valid_items.groupby('product_name')['quantity'].sum().reset_index()
        top_prods = top_prods.sort_values('quantity', ascending=True).tail(10)

        fig5 = px.bar(
            top_prods,
            x='quantity',
            y='product_name',
            orientation='h',
            title="Top 10 Products by Units Sold",
            labels={'quantity': 'Units Sold', 'product_name': 'Product'},
            color_discrete_sequence=['#6366f1']
        )
        fig5.update_layout(**chart_layout)
        charts['top_products'] = fig5.to_html(full_html=False, include_plotlyjs=False)

    # Chart 6: Sales by City
    if not df_valid_orders.empty:
        city_sales = df_valid_orders.groupby('shipping_city')['total_amount'].sum().reset_index()
        city_sales = city_sales.sort_values('total_amount', ascending=False).head(8)

        fig6 = px.bar(
            city_sales,
            x='shipping_city',
            y='total_amount',
            title="Geographic Sales by City (₹)",
            labels={'shipping_city': 'City', 'total_amount': 'Sales (₹)'},
            color_discrete_sequence=['#f59e0b']
        )
        fig6.update_layout(**chart_layout)
        charts['city_sales'] = fig6.to_html(full_html=False, include_plotlyjs=False)

    # Chart 7: Order Status Distribution (Donut Chart)
    if not df_orders.empty:
        status_counts = df_orders['status'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']

        fig7 = px.pie(
            status_counts,
            values='count',
            names='status',
            hole=0.5,
            title="Order Status Distribution",
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig7.update_layout(**chart_layout)
        charts['status_distribution'] = fig7.to_html(full_html=False, include_plotlyjs=False)

    # Chart 8: New vs Returning Customers
    if not df_valid_orders.empty:
        cust_type_df = pd.DataFrame({
            'Type': ['New / 1-Time Customer', 'Repeat Customer'],
            'Count': [total_customers_with_orders - repeat_customers_count, repeat_customers_count]
        })
        fig8 = px.pie(
            cust_type_df,
            values='Count',
            names='Type',
            hole=0.45,
            title="Customer Retention Breakdown",
            color_discrete_sequence=['#94a3b8', '#3b82f6']
        )
        fig8.update_layout(**chart_layout)
        charts['customer_types'] = fig8.to_html(full_html=False, include_plotlyjs=False)

    return {
        'kpis': kpis,
        'insights': insights,
        'charts': charts
    }
