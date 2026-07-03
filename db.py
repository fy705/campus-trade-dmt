import pymssql
from config import DB_CONFIG

# 中文乱码统一修复函数
def _fix_chinese(text):
    if text is None or not isinstance(text, str):
        return text
    try:
        return text.encode('latin-1').decode('gbk')
    except(UnicodeEncodeError, UnicodeDecodeError):
        return text

def get_conn():
    conn = pymssql.connect(
        server=DB_CONFIG['server'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset='utf8'
    )
    return conn

def query_one(sql, args=None):
    conn = get_conn()
    cursor = conn.cursor(as_dict=True)
    cursor.execute(sql, args)
    result = cursor.fetchone()
    conn.close()
    if result:
        for k, v in result.items():
            result[k] = _fix_chinese(v)
    return result

def query_all(sql, args=None):
    conn = get_conn()
    cursor = conn.cursor(as_dict=True)
    cursor.execute(sql, args)
    result = cursor.fetchall()
    conn.close()
    for row in result:
        for k, v in row.items():
            row[k] = _fix_chinese(v)
    return result

def execute_sql(sql, args=None):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, args)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print("数据库操作错误:", e)
        return False
    finally:
        conn.close()