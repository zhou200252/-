from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
from decimal import Decimal
import json
from datetime import datetime

app = Flask(__name__)
CORS(app, methods=["POST", "GET", "OPTIONS"], allow_headers=["Content-Type"])

# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'order_list',
    'cursorclass': pymysql.cursors.DictCursor
}

# 连接到数据库
def get_db_connection():
    return pymysql.connect(**db_config)

@app.route('/')
def home():
    return "欢迎使用购物车系统！请使用前端页面进行操作。"

@app.route('/checkout', methods=['POST', 'OPTIONS'])
def checkout():
    if request.method == 'OPTIONS':
        # 处理 OPTIONS 预检请求
        response = jsonify({'message': 'Preflight request allowed'})
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 200

    data = request.json
    if not data or 'items' not in data or 'total_price' not in data or 'customer' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    customer_name = data['customer']['name']
    customer_phone = data['customer']['phone']
    total_price = data['total_price']
    items = json.dumps(data['items'])

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO orders (customer_name, customer_phone, total_price, items)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (customer_name, customer_phone, total_price, items))
        connection.commit()
    except Exception as e:
        print(f"Error saving order to database: {e}")
        return jsonify({'error': 'Failed to save order'}), 500
    finally:
        connection.close()

    return jsonify({'message': 'Order received and saved successfully!'}), 200

@app.route('/api/orders', methods=['GET'])
def get_orders():
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))  # 当前页码，默认为 1
        per_page = int(request.args.get('per_page', 5))  # 每页条数，默认为 5
        search = request.args.get('search', '')  # 搜索关键字
        min_price = request.args.get('min_price')  # 最小金额
        max_price = request.args.get('max_price')  # 最大金额
        start_date = request.args.get('start_date')  # 开始时间
        end_date = request.args.get('end_date')  # 结束时间
        specific_date = request.args.get('specific_date')  # 具体日期

        # 白名单验证
        valid_sort_fields = ['created_at', 'total_price']
        valid_sort_orders = ['asc', 'desc']

        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')

        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        if sort_order not in valid_sort_orders:
            sort_order = 'desc'

        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 基础查询
            sql = """
            SELECT * FROM orders
            WHERE (customer_name LIKE %s OR customer_phone LIKE %s)
            """
            params = [f'%{search}%', f'%{search}%']

            # 添加金额范围筛选
            if min_price:
                sql += " AND total_price >= %s"
                params.append(float(min_price))
            if max_price:
                sql += " AND total_price <= %s"
                params.append(float(max_price))

            # 添加时间范围筛选
            if start_date and end_date:
                sql += " AND created_at BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            elif specific_date:
                sql += " AND DATE(created_at) = %s"
                params.append(specific_date)

            # 添加排序和分页
            sql += " ORDER BY {} {} LIMIT %s OFFSET %s".format(sort_by, sort_order)
            params.extend([per_page, (page - 1) * per_page])

            cursor.execute(sql, params)
            orders = cursor.fetchall()

            # 查询总条数
            count_sql = """
            SELECT COUNT(*) as total FROM orders
            WHERE (customer_name LIKE %s OR customer_phone LIKE %s)
            """
            count_params = [f'%{search}%', f'%{search}%']

            if min_price:
                count_sql += " AND total_price >= %s"
                count_params.append(float(min_price))
            if max_price:
                count_sql += " AND total_price <= %s"
                count_params.append(float(max_price))
            if start_date and end_date:
                count_sql += " AND created_at BETWEEN %s AND %s"
                count_params.extend([start_date, end_date])
            elif specific_date:
                count_sql += " AND DATE(created_at) = %s"
                count_params.append(specific_date)

            cursor.execute(count_sql, count_params)
            total = cursor.fetchone()['total']

        # 将 Decimal 类型转换为 float
        for order in orders:
            if isinstance(order['total_price'], Decimal):
                order['total_price'] = float(order['total_price'])

        return jsonify({
            'orders': orders,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        print(f"Error fetching orders from database: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)