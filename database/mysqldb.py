import os
import pandas as pd
from typing import Dict, Any, List
from mysql.connector import pooling, Error
from dotenv import load_dotenv

class MySQLConnectionManager:
    """MySQL数据库连接管理器，实现单例模式"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MySQLConnectionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        初始化MySQL连接管理器。
        从环境变量加载配置并创建连接池。
        """
        if self._initialized:
            return
            
        load_dotenv()
        
        self.db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
        }

        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="mysql_pool",
                pool_size=5,
                **self.db_config
            )
            print("MySQL connection pool created successfully.")
        except Error as e:
            print(f"Error while creating MySQL connection pool: {e}")
            self.pool = None

        self._initialized = True

    def get_connection(self):
        """从连接池获取一个数据库连接"""
        if self.pool:
            try:
                return self.pool.get_connection()
            except Error as e:
                print(f"Error getting connection from pool: {e}")
                return None
        return None

    def execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        """
        执行SQL查询并返回结果作为pandas DataFrame。

        参数:
            query (str): 要执行的SQL查询语句。
            params (tuple, optional): 查询参数。 Defaults to None.

        返回:
            pd.DataFrame: 查询结果。
        """
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            
            result = cursor.fetchall()
            df = pd.DataFrame(result)
            
            cursor.close()
            return df
        except Error as e:
            print(f"Error executing query: {e}")
            return pd.DataFrame()
        finally:
            if conn.is_connected():
                conn.close()

    def execute_many(self, query: str, data: List[tuple]) -> bool:
        """
        执行批量插入或更新操作。

        参数:
            query (str): 要执行的SQL语句 (例如, INSERT, UPDATE)。
            data (List[tuple]): 要插入或更新的数据列表。

        返回:
            bool: 操作是否成功。
        """
        conn = self.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            cursor.close()
            return True
        except Error as e:
            print(f"Error during batch execution: {e}")
            conn.rollback()
            return False
        finally:
            if conn.is_connected():
                conn.close()

    def close(self):
        """关闭连接池 (在应用退出时调用)"""
        # Connection pool does not have an explicit close method.
        # Connections are returned to the pool and managed automatically.
        # This method is for interface consistency.
        print("MySQL connection manager is shutting down.")
        pass

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 提供便捷的全局访问点
mysql_db_manager = MySQLConnectionManager()

def get_db_manager() -> MySQLConnectionManager:
    """获取MySQL数据库连接管理器实例"""
    return mysql_db_manager