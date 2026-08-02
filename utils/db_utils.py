# -*- coding: utf-8 -*-
"""数据库连接与通用查询工具"""
import os
import re
import sqlite3
from contextlib import closing


def natural_key(s):
    """自然排序键：数字部分按数值比较（Slot2 < Slot10，Fi_10GE_2 < Fi_10GE_10）"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s or '')]

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db')
DB_PATH = os.path.join(DB_DIR, 'network.db')


def get_conn():
    """获取数据库连接（自动建目录、启用外键与行字典模式）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def query_all(sql, params=()):
    """查询多行，返回 dict 列表"""
    with closing(get_conn()) as conn, conn:
        return [dict(r) for r in conn.execute(sql, params)]


def query_one(sql, params=()):
    """查询单行，返回 dict 或 None"""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """执行写操作，返回 lastrowid"""
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid
