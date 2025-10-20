import pymysql
from faker import Faker
from datetime import timedelta
import random
from dotenv import load_dotenv
import os

# 初始化Faker
fake = Faker('zh_CN')
Faker.seed(42)  # 固定随机种子，确保数据可复现

# 数据库连接配置
load_dotenv()
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'charset': 'utf8mb4'
}

def create_database_and_tables():
    """创建数据库和表（如果不存在）"""
    conn = pymysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        charset=db_config["charset"]
    )
    cursor = conn.cursor()
    
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
    conn.select_db(db_config["database"])
    
    create_table_sqls = [
        # 用户表
        """
        CREATE TABLE IF NOT EXISTS `user` (
            `user_id` INT PRIMARY KEY AUTO_INCREMENT,
            `username` VARCHAR(50) NOT NULL,
            `phone` VARCHAR(20) NOT NULL,
            `address` VARCHAR(200) NOT NULL,
            `register_time` DATETIME NOT NULL
        )
        """,
        # 商品分类表
        """
        CREATE TABLE IF NOT EXISTS `product_category` (
            `category_id` INT PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(50) NOT NULL,
            `parent_id` INT NOT NULL DEFAULT 0
        )
        """,
        # 商品表
        """
        CREATE TABLE IF NOT EXISTS `product` (
            `product_id` INT PRIMARY KEY AUTO_INCREMENT,
            `name` VARCHAR(100) NOT NULL,
            `price` DECIMAL(10,2) NOT NULL,
            `stock` INT NOT NULL,
            `category_id` INT NOT NULL
        )
        """,
        # 订单表
        """
        CREATE TABLE IF NOT EXISTS `order` (
            `order_id` INT PRIMARY KEY AUTO_INCREMENT,
            `user_id` INT NOT NULL,
            `total_amount` DECIMAL(10,2) NOT NULL,
            `order_status` VARCHAR(20) NOT NULL,
            `create_time` DATETIME NOT NULL
        )
        """,
        # 订单项表
        """
        CREATE TABLE IF NOT EXISTS `order_item` (
            `item_id` INT PRIMARY KEY AUTO_INCREMENT,
            `order_id` INT NOT NULL,
            `product_id` INT NOT NULL,
            `quantity` INT NOT NULL,
            `item_price` DECIMAL(10,2) NOT NULL
        )
        """,
        # 支付表
        """
        CREATE TABLE IF NOT EXISTS `payment` (
            `payment_id` INT PRIMARY KEY AUTO_INCREMENT,
            `order_id` INT NOT NULL,
            `pay_amount` DECIMAL(10,2) NOT NULL,
            `pay_method` VARCHAR(20) NOT NULL,
            `pay_time` DATETIME NOT NULL
        )
        """
    ]
    
    for sql in create_table_sqls:
        cursor.execute(sql)
    conn.commit()
    conn.close()
    print("数据库和表创建完成（若不存在）")


def generate_categories(num=5):
    db = pymysql.connect(**db_config)
    cursor = db.cursor()
    categories = ["电子产品", "服装鞋帽", "食品饮料", "家居用品", "图书音像"]
    for i in range(num):
        cursor.execute(
            "INSERT INTO product_category (name, parent_id) VALUES (%s, 0)",
            (categories[i],)
        )
    sub_categories = {
        1: ["手机", "电脑", "耳机"],
        2: ["男装", "女装", "童装"],
        3: ["零食", "饮料", "生鲜"]
    }
    for parent_id, sub_names in sub_categories.items():
        for name in sub_names:
            cursor.execute(
                "INSERT INTO product_category (name, parent_id) VALUES (%s, %s)",
                (name, parent_id)
            )
    db.commit()
    db.close()
    print(f"生成了{num + sum(len(v) for v in sub_categories.values())}条商品分类数据")


def generate_products(num=200):
    db = pymysql.connect(** db_config)
    cursor = db.cursor()
    cursor.execute("SELECT category_id FROM product_category")
    category_ids = [row[0] for row in cursor.fetchall()]
    if not category_ids:
        raise ValueError("请先生成商品分类")

    for _ in range(num):
        name = fake.catch_phrase() + " " + fake.word()
        price = round(random.uniform(10, 2000), 2)
        stock = random.randint(0, 1000)
        category_id = random.choice(category_ids)
        cursor.execute(
            "INSERT INTO product (name, price, stock, category_id) VALUES (%s, %s, %s, %s)",
            (name, price, stock, category_id)
        )
    db.commit()
    db.close()
    print(f"生成了{num}条商品数据")


def generate_users(num=100):
    db = pymysql.connect(**db_config)
    cursor = db.cursor()
    for _ in range(num):
        username = fake.user_name()
        phone = fake.phone_number()
        address = fake.address().replace("\n", "")
        register_time = fake.date_time_between(start_date="-1y", end_date="now")
        cursor.execute(
            "INSERT INTO user (username, phone, address, register_time) VALUES (%s, %s, %s, %s)",
            (username, phone, address, register_time)
        )
    db.commit()
    db.close()
    print(f"生成了{num}条用户数据")


def generate_orders(num=500):
    db = pymysql.connect(** db_config)
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM user")
    user_ids = [row[0] for row in cursor.fetchall()]
    if not user_ids:
        raise ValueError("请先生成用户")

    status_list = ["pending", "paid", "shipped", "delivered", "cancelled"]
    for _ in range(num):
        user_id = random.choice(user_ids)
        total_amount = 0
        order_status = random.choice(status_list)
        create_time = fake.date_time_between(start_date="-6m", end_date="now")
        cursor.execute(
            "INSERT INTO `order` (user_id, total_amount, order_status, create_time) VALUES (%s, %s, %s, %s)",
            (user_id, total_amount, order_status, create_time)
        )
    db.commit()
    db.close()
    print(f"生成了{num}条订单数据")


def generate_order_items(avg_items_per_order=2):
    db = pymysql.connect(**db_config)
    cursor = db.cursor()
    cursor.execute("SELECT order_id FROM `order`")
    order_ids = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT product_id, price FROM product")
    products = [(row[0], row[1]) for row in cursor.fetchall()]
    if not order_ids or not products:
        raise ValueError("请先生成订单和商品")

    for order_id in order_ids:
        item_count = random.randint(1, avg_items_per_order + 3)
        total = 0
        for _ in range(item_count):
            product_id, price = random.choice(products)
            quantity = random.randint(1, 10)
            item_price = price
            total += quantity * item_price
            cursor.execute(
                "INSERT INTO order_item (order_id, product_id, quantity, item_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, item_price)
            )
        cursor.execute(
            "UPDATE `order` SET total_amount = %s WHERE order_id = %s",
            (round(total, 2), order_id)
        )
    db.commit()
    db.close()
    print(f"生成了约{len(order_ids) * avg_items_per_order}条订单项数据")


def generate_payments():
    db = pymysql.connect(** db_config)
    cursor = db.cursor()
    cursor.execute("""
        SELECT order_id, total_amount, create_time 
        FROM `order` 
        WHERE order_status IN ('paid', 'shipped', 'delivered')
    """)
    valid_orders = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    if not valid_orders:
        raise ValueError("请先生成订单（需包含已支付状态）")

    pay_methods = ["alipay", "wechat", "credit_card", "cash"]
    for order_id, total_amount, create_time in valid_orders:
        pay_delay = timedelta(minutes=random.randint(10, 1440))
        pay_time = create_time + pay_delay
        cursor.execute(
            "INSERT INTO payment (order_id, pay_amount, pay_method, pay_time) VALUES (%s, %s, %s, %s)",
            (order_id, total_amount, random.choice(pay_methods), pay_time)
        )
    db.commit()
    db.close()
    print(f"生成了{len(valid_orders)}条支付记录")


if __name__ == "__main__":
    try:
        create_database_and_tables()
        generate_categories()
        generate_products()
        generate_users()
        generate_orders()
        generate_order_items()
        generate_payments()
        print("\n✅ 所有操作完成！数据已成功生成")
    except Exception as e:
        print(f"\n❌ 操作失败：{str(e)}")