import mysql.connector
from faker import Faker
from datetime import timedelta
import random
from dotenv import load_dotenv
import os

# 初始化Faker
fake = Faker('zh_CN')

# 数据库连接配置 - 请修改为你的数据库信息
load_dotenv()
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', '3306')),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
}

def create_table_if_not_exists():
    """检查数据表是否存在，不存在则创建"""
    try:
        # 连接数据库
        conn = mysql.connector.connect(** db_config)
        cursor = conn.cursor()
        
        # 创建表的SQL语句
        create_table_query = """
        CREATE TABLE IF NOT EXISTS data_test (
            p_id BIGINT,
            p_describe TEXT,
            t1_start_schedule DATETIME NOT NULL,
            t1_end_schedule DATETIME NOT NULL,
            t1_start_actual DATETIME NULL,
            t1_end_actual DATETIME NULL,
            t2_start_schedule DATETIME NOT NULL,
            t2_end_schedule DATETIME NOT NULL,
            t2_start_actual DATETIME NULL,
            t2_end_actual DATETIME NULL
        )
        """
        
        cursor.execute(create_table_query)
        conn.commit()
        print("数据表检查/创建完成")
        
    except mysql.connector.Error as err:
        print(f"创建表时出错: {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def generate_time_pair(previous_end=None):
    """生成时间对(开始时间, 结束时间)，确保开始时间早于结束时间"""
    # 如果有前一个阶段的结束时间，当前开始时间要晚于该时间
    if previous_end:
        start = previous_end + timedelta(minutes=random.randint(10, 120))
    else:
        # 随机生成一个基础开始时间（近30天内）
        start = fake.date_time_between(start_date='-30d', end_date='now')
    
    # 结束时间在开始时间之后，间隔1-24小时
    end_delta = timedelta(hours=random.randint(1, 24))
    end = start + end_delta
    
    return start, end

def generate_actual_time(schedule_start, schedule_end):
    """生成实际时间，可能为空，遵循规则"""
    # 50%概率有实际时间
    has_actual = random.choice([True, False])
    
    if not has_actual:
        return (None, None)
    
    # 实际开始时间在计划开始时间前后1天内，但不早于计划开始时间太多
    start_delta = timedelta(hours=random.randint(-12, 24))
    actual_start = schedule_start + start_delta
    if actual_start < schedule_start - timedelta(days=1):
        actual_start = schedule_start - timedelta(days=1)
    
    # 30%概率只有实际开始时间，没有结束时间
    has_end = random.choices([True, False], weights=[0.7, 0.3])[0]
    
    if not has_end:
        return (actual_start, None)
    
    # 实际结束时间在实际开始时间之后，且可能在计划结束时间前后
    end_delta = timedelta(hours=random.randint(1, 48))
    actual_end = actual_start + end_delta
    
    return (actual_start, actual_end)

def generate_test_data(num_records=10):
    """生成指定数量的测试数据"""
    data = []
    
    for _ in range(num_records):
        # 生成p_id (假设为10位数字)
        p_id = fake.random_number(digits=10, fix_len=True)
        
        # 生成描述
        p_describe = fake.text(max_nb_chars=200)
        
        # 生成t1计划时间
        t1_start_schedule, t1_end_schedule = generate_time_pair()
        
        # 生成t1实际时间
        t1_start_actual, t1_end_actual = generate_actual_time(
            t1_start_schedule, t1_end_schedule
        )
        
        # 生成t2计划时间，必须晚于t1计划结束时间
        t2_start_schedule, t2_end_schedule = generate_time_pair(t1_end_schedule)
        
        # 生成t2实际时间
        t2_start_actual, t2_end_actual = generate_actual_time(
            t2_start_schedule, t2_end_schedule
        )
        
        # 整理数据
        record = (
            p_id,
            p_describe,
            t1_start_schedule,
            t1_end_schedule,
            t1_start_actual,
            t1_end_actual,
            t2_start_schedule,
            t2_end_schedule,
            t2_start_actual,
            t2_end_actual
        )
        
        data.append(record)
    
    return data

def insert_into_database(data):
    """将数据插入到MySQL数据库"""
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 插入数据的SQL语句
        insert_query = """
        INSERT INTO data_test (
            p_id, p_describe, t1_start_schedule, t1_end_schedule,
            t1_start_actual, t1_end_actual, t2_start_schedule, t2_end_schedule,
            t2_start_actual, t2_end_actual
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # 执行批量插入
        cursor.executemany(insert_query, data)
        conn.commit()
        
        print(f"成功插入 {cursor.rowcount} 条记录")
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        conn.rollback()
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    # 先检查并创建表
    create_table_if_not_exists()
    
    # 生成100条测试数据，可以根据需要调整数量
    test_data = generate_test_data(500)
    
    # 插入到数据库
    insert_into_database(test_data)
    