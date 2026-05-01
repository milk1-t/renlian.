# encoding:utf-8
"""MySQL 数据库操作模块"""
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

# MySQL 配置（可通过环境变量覆盖）
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'face_recognition')


def get_conn(database=None):
    """获取数据库连接"""
    if not HAS_PYMYSQL:
        raise RuntimeError('请安装 PyMySQL: pip install PyMySQL')
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=database or MYSQL_DATABASE,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def ensure_database():
    """若数据库不存在则自动创建"""
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset='utf8mb4'
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` DEFAULT CHARSET utf8mb4")
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    ensure_database()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `user` (
                  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
                  `username` VARCHAR(64) NOT NULL COMMENT '用户名',
                  `password` VARCHAR(128) NOT NULL COMMENT '密码',
                  `name` VARCHAR(64) NULL COMMENT '昵称',
                  `role` VARCHAR(32) NULL COMMENT '角色',
                  PRIMARY KEY (`id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表'
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `analysis` (
                  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
                  `user_id` INT NULL COMMENT '用户ID',
                  `username` VARCHAR(64) NOT NULL COMMENT '用户名',
                  `image_path` VARCHAR(512) NULL COMMENT '图片路径',
                  `created_at` DATETIME NOT NULL COMMENT '创建时间',
                  `payload_json` LONGTEXT NOT NULL COMMENT '分析数据',
                  PRIMARY KEY (`id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析记录表'
            """)
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """根据用户名获取用户"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, password, name, role FROM `user` WHERE username = %s", (username,))
            return cur.fetchone()
    finally:
        conn.close()


def create_user(username: str, password: str, name: str = None, role: str = 'user') -> bool:
    """创建用户"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO `user` (username, password, name, role) VALUES (%s, %s, %s, %s)",
                (username, password, name or username, role)
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def save_analysis(username: str, payload: Dict[str, Any], image_path: str = None) -> int:
    """保存分析记录，返回自增 id"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analysis (username, image_path, created_at, payload_json) VALUES (%s, %s, %s, %s)",
                (username, image_path, datetime.utcnow(), json.dumps(payload, ensure_ascii=False))
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def load_analysis_list(username: str, limit: int = 100) -> List[Dict[str, Any]]:
    """获取用户分析记录列表（按时间倒序）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, username, image_path, created_at 
                   FROM analysis WHERE username = %s 
                   ORDER BY created_at DESC, id DESC LIMIT %s""",
                (username, limit)
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def load_analysis_by_id(record_id: int, username: str = None) -> Optional[Dict[str, Any]]:
    """根据 id 获取单条分析记录"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if username:
                cur.execute(
                    "SELECT id, username, image_path, created_at, payload_json FROM analysis WHERE id = %s AND username = %s",
                    (record_id, username)
                )
            else:
                cur.execute(
                    "SELECT id, username, image_path, created_at, payload_json FROM analysis WHERE id = %s",
                    (record_id,)
                )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get('payload_json'):
                d['payload_json'] = json.loads(d['payload_json'])
            return d
    finally:
        conn.close()


def delete_analysis(record_id: int, username: str = None) -> bool:
    """删除单条分析记录"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if username:
                cur.execute("DELETE FROM analysis WHERE id = %s AND username = %s", (record_id, username))
            else:
                cur.execute("DELETE FROM analysis WHERE id = %s", (record_id,))
            n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def delete_analysis_batch(record_ids: List[int], username: str = None) -> int:
    """批量删除分析记录，返回删除条数"""
    if not record_ids:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(record_ids))
            if username:
                sql = f"DELETE FROM analysis WHERE id IN ({placeholders}) AND username = %s"
                cur.execute(sql, record_ids + [username])
            else:
                sql = f"DELETE FROM analysis WHERE id IN ({placeholders})"
                cur.execute(sql, record_ids)
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()
