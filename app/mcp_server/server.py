import json
from mcp.server.fastmcp import FastMCP
from typing import Optional
from app.database.db import execute_query_df

# Initialize FastMCP server
mcp = FastMCP("EcommerceAnalytics")

def to_json(df):
    """Helper to convert DataFrame to JSON string safely."""
    if df.empty:
        return json.dumps([])
    return df.to_json(orient="records")

@mcp.tool()
def get_order_trends(
    metric: str, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None,
    group_by: Optional[str] = 'month'
) -> str:
    """
    Get order trends.
    metric: 'revenue', 'orders', or 'delivery'
    group_by: 'month' or 'state'
    """
    try:
        if metric not in ['revenue', 'orders', 'delivery']:
            return json.dumps({"error": "Invalid metric.", "tool": "get_order_trends"})

        where_clauses = []
        params = []
        if start_date and end_date:
            where_clauses.append("date(o.order_purchase_timestamp) BETWEEN ? AND ?")
            params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("date(o.order_purchase_timestamp) >= ?")
            params.append(start_date)
        elif end_date:
            where_clauses.append("date(o.order_purchase_timestamp) <= ?")
            params.append(end_date)
            
        if metric == 'delivery':
            where_clauses.append("o.order_delivered_customer_date IS NOT NULL")
            
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        group_col = "strftime('%Y-%m', o.order_purchase_timestamp) as month" if group_by == 'month' else "c.customer_state as state"
        group_by_col = "month" if group_by == 'month' else "state"
        
        join_clause = "JOIN olist_customers_dataset c ON o.customer_id = c.customer_id" if group_by == 'state' else ""
        
        if metric == 'revenue':
            query = f"""
                SELECT {group_col}, SUM(p.payment_value) as revenue
                FROM olist_orders_dataset o
                JOIN olist_order_payments_dataset p ON o.order_id = p.order_id
                {join_clause}
                {where_clause}
                GROUP BY {group_by_col}
                ORDER BY {group_by_col}
            """
        elif metric == 'orders':
            query = f"""
                SELECT {group_col}, COUNT(o.order_id) as orders
                FROM olist_orders_dataset o
                {join_clause}
                {where_clause}
                GROUP BY {group_by_col}
                ORDER BY {group_by_col}
            """
        elif metric == 'delivery':
            query = f"""
                SELECT {group_col}, 
                       AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)) as delivery_delay
                FROM olist_orders_dataset o
                {join_clause}
                {where_clause}
                GROUP BY {group_by_col}
                ORDER BY {group_by_col}
            """

        df = execute_query_df(query, tuple(params))
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_order_trends"})

@mcp.tool()
def get_product_category_performance(category_name_english: Optional[str] = None, limit: int = 10, sort_by: str = 'revenue') -> str:
    """
    Get product category performance (revenue, order count, average review score).
    category_name_english: Filter by specific category (optional)
    limit: Top N results
    sort_by: 'revenue', 'orders', or 'review_score'
    """
    try:
        if sort_by not in ['revenue', 'orders', 'review_score']:
            return json.dumps({"error": "Invalid sort_by. Choose revenue, orders, or review_score.", "tool": "get_product_category_performance"})

        where_clause = ""
        params = ()
        if category_name_english:
            where_clause = "WHERE t.product_category_name_english = ?"
            params = (category_name_english,)

        if sort_by == 'revenue':
            order_clause = "total_revenue DESC"
            select_clause = """t.product_category_name_english as category,
                   SUM(oi.price) as total_revenue"""
        elif sort_by == 'orders':
            order_clause = "order_volume DESC"
            select_clause = """t.product_category_name_english as category,
                   COUNT(o.order_id) as order_volume,
                   AVG(r.review_score) as average_review_score"""
        else:
            order_clause = "avg_review_score DESC"
            select_clause = """t.product_category_name_english as category,
                   SUM(oi.price) as total_revenue,
                   AVG(r.review_score) as avg_review_score"""

        query = f"""
            SELECT {select_clause}
            FROM olist_order_items_dataset oi
            JOIN olist_products_dataset p ON oi.product_id = p.product_id
            JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
            JOIN olist_orders_dataset o ON oi.order_id = o.order_id
            LEFT JOIN olist_order_reviews_dataset r ON o.order_id = r.order_id
            {where_clause}
            GROUP BY category
            ORDER BY {order_clause}
            LIMIT {limit}
        """

        df = execute_query_df(query, params)
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_product_category_performance"})

@mcp.tool()
def get_seller_performance(state: Optional[str] = None, limit: int = 10, sort_order: str = 'desc') -> str:
    """
    Get top sellers by revenue.
    state: filter by seller state code (e.g. 'SP') (optional)
    sort_order: 'desc' (top sellers) or 'asc' (worst sellers)
    """
    try:
        sort_order = sort_order.upper()
        if sort_order not in ['ASC', 'DESC']:
            return json.dumps({"error": "Invalid sort_order", "tool": "get_seller_performance"})

        where_clause = ""
        params = ()
        if state:
            where_clause = "WHERE s.seller_state = ?"
            params = (state,)

        query = f"""
            SELECT s.seller_id, s.seller_city, s.seller_state, SUM(oi.price) as total_revenue
            FROM olist_sellers_dataset s
            JOIN olist_order_items_dataset oi ON s.seller_id = oi.seller_id
            {where_clause}
            GROUP BY s.seller_id, s.seller_city, s.seller_state
            ORDER BY total_revenue {sort_order}
            LIMIT {limit}
        """
        df = execute_query_df(query, params)
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_seller_performance"})

@mcp.tool()
def get_customer_reviews(
    category_name_english: Optional[str] = None,
    group_by: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    Get customer reviews.
    group_by: 'month' or 'state'. If None, returns review score distribution.
    """
    try:
        where_clauses = []
        params = []
        if category_name_english:
            where_clauses.append("""
                o.order_id IN (
                    SELECT oi.order_id FROM olist_order_items_dataset oi
                    JOIN olist_products_dataset p ON oi.product_id = p.product_id
                    JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
                    WHERE t.product_category_name_english = ?
                )
            """)
            params.append(category_name_english)
            
        if start_date and end_date:
            where_clauses.append("date(o.order_purchase_timestamp) BETWEEN ? AND ?")
            params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("date(o.order_purchase_timestamp) >= ?")
            params.append(start_date)
        elif end_date:
            where_clauses.append("date(o.order_purchase_timestamp) <= ?")
            params.append(end_date)
            
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        if group_by == 'month':
            query = f"""
                SELECT strftime('%Y-%m', o.order_purchase_timestamp) as month,
                       AVG(r.review_score) as average_review_score
                FROM olist_order_reviews_dataset r
                JOIN olist_orders_dataset o ON r.order_id = o.order_id
                {where_clause}
                GROUP BY month
                ORDER BY month
            """
        elif group_by == 'state':
            query = f"""
                SELECT c.customer_state as state,
                       AVG(r.review_score) as average_review_score
                FROM olist_order_reviews_dataset r
                JOIN olist_orders_dataset o ON r.order_id = o.order_id
                JOIN olist_customers_dataset c ON o.customer_id = c.customer_id
                {where_clause}
                GROUP BY state
                ORDER BY state
            """
        else:
            query = f"""
                SELECT r.review_score, COUNT(*) as count
                FROM olist_order_reviews_dataset r
                JOIN olist_orders_dataset o ON r.order_id = o.order_id
                {where_clause}
                GROUP BY r.review_score
                ORDER BY r.review_score
            """
            
        df = execute_query_df(query, tuple(params))
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_customer_reviews"})

@mcp.tool()
def get_seller_delivery_review_correlation(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """
    Get correlation between delivery time and average review score by seller.
    """
    try:
        where_clauses = ["o.order_delivered_customer_date IS NOT NULL", "r.review_score IS NOT NULL"]
        params = []
            
        if start_date and end_date:
            where_clauses.append("date(o.order_purchase_timestamp) BETWEEN ? AND ?")
            params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("date(o.order_purchase_timestamp) >= ?")
            params.append(start_date)
        elif end_date:
            where_clauses.append("date(o.order_purchase_timestamp) <= ?")
            params.append(end_date)
            
        where_clause = "WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                s.seller_id,
                AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)) as avg_delivery_delay,
                AVG(r.review_score) as avg_review_score
            FROM olist_sellers_dataset s
            JOIN olist_order_items_dataset oi ON s.seller_id = oi.seller_id
            JOIN olist_orders_dataset o ON oi.order_id = o.order_id
            JOIN olist_order_reviews_dataset r ON o.order_id = r.order_id
            {where_clause}
            GROUP BY s.seller_id
            HAVING COUNT(o.order_id) >= 10
        """
        df = execute_query_df(query, tuple(params))
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_seller_delivery_review_correlation"})

@mcp.tool()
def get_payment_breakdown(
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None,
    payment_types: Optional[list[str]] = None
) -> str:
    """
    Get share of different payment types.
    payment_types: filter by specific payment types (e.g. ['credit_card', 'boleto'])
    """
    try:
        where_clauses = []
        params = []

        if start_date and end_date:
            where_clauses.append("date(o.order_purchase_timestamp) BETWEEN ? AND ?")
            params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("date(o.order_purchase_timestamp) >= ?")
            params.append(start_date)
        elif end_date:
            where_clauses.append("date(o.order_purchase_timestamp) <= ?")
            params.append(end_date)

        if payment_types:
            placeholders = ",".join(["?"] * len(payment_types))
            where_clauses.append(f"p.payment_type IN ({placeholders})")
            params.extend(payment_types)

        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        join_clause = "JOIN olist_orders_dataset o ON p.order_id = o.order_id" if (start_date or end_date) else ""

        query = f"""
            SELECT p.payment_type, COUNT(*) as count, SUM(p.payment_value) as total_value
            FROM olist_order_payments_dataset p
            {join_clause}
            {where_clause}
            GROUP BY p.payment_type
            ORDER BY count DESC
        """
        df = execute_query_df(query, tuple(params))
        if not df.empty and 'count' in df.columns:
            total_count = df['count'].sum()
            if total_count > 0:
                df['share'] = (df['count'] / total_count * 100).round(2)
        return to_json(df)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": "get_payment_breakdown"})


if __name__ == "__main__":
    mcp.run()
