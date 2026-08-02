# -*- coding: utf-8 -*-
"""
LLD 网络连接管理工具 - 数据库初始化脚本
创建全部表结构并导入种子数据（幂等，可重复执行）
"""
import os
import sqlite3

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db')
DB_PATH = os.path.join(DB_DIR, 'network.db')

SCHEMA = """
-- 1. 设备模板表（类型由用户输入决定：network=网络设备 / server=服务器 / other=其它设备，不做程序推断）
CREATE TABLE IF NOT EXISTS device_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT UNIQUE NOT NULL,
    vendor TEXT,
    type TEXT,
    description TEXT
);

-- 2. 端口模板表（端口名 = 完整接口名，如 Slot2_Fi_10GE_41）
CREATE TABLE IF NOT EXISTS port_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_template_id INTEGER NOT NULL,
    port_name TEXT NOT NULL,
    FOREIGN KEY (device_template_id) REFERENCES device_templates(id) ON DELETE CASCADE,
    UNIQUE(device_template_id, port_name)
);

-- 4. 项目表
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 项目设备实例表（template_id 为 NULL 表示自由输入设备）
CREATE TABLE IF NOT EXISTS project_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    template_id INTEGER,
    name TEXT NOT NULL,
    location TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES device_templates(id)
);

-- 6. 项目端口实例表（interface_status 值来自全局接口状态字典）
CREATE TABLE IF NOT EXISTS project_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_device_id INTEGER NOT NULL,
    template_port_id INTEGER,
    port_name TEXT NOT NULL,
    is_used BOOLEAN DEFAULT 0,
    interface_status TEXT DEFAULT 'Down',
    FOREIGN KEY (project_device_id) REFERENCES project_devices(id) ON DELETE CASCADE,
    FOREIGN KEY (template_port_id) REFERENCES port_templates(id)
);

-- 7. 项目连接表（Cable 模型：一条物理链路一行，port_a < port_b，两端自动可见）
CREATE TABLE IF NOT EXISTS project_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    port_a_id INTEGER NOT NULL,
    port_b_id INTEGER NOT NULL,
    aggregation_group_a TEXT,
    aggregation_group_b TEXT,
    aggregation_mode TEXT,
    interface_mode TEXT,
    vlan_id TEXT,
    description TEXT,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (port_a_id) REFERENCES project_ports(id),
    FOREIGN KEY (port_b_id) REFERENCES project_ports(id),
    UNIQUE(port_a_id, port_b_id)
);

-- 8. 全局选项字典（设备角色 / 接口状态 / 聚合模式 / 接口模式，用户可扩充）
CREATE TABLE IF NOT EXISTS option_dicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    UNIQUE(category, value)
);

-- 9. 项目级 VLAN 字典（每个项目独立维护）
CREATE TABLE IF NOT EXISTS project_vlans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    name TEXT,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, value)
);
"""


def _add_port(conn, template_id, port_name):
    """插入端口（端口名 = 完整接口名），已存在则忽略"""
    conn.execute(
        'INSERT OR IGNORE INTO port_templates (device_template_id, port_name) VALUES (?,?)',
        (template_id, port_name))


def _add_ports_range(conn, template_id, prefix, start, end, width=2):
    """批量生成 Fi_10GE_01 ~ Fi_10GE_48 这类规则化端口名"""
    for i in range(start, end + 1):
        name = f'{prefix}{i:0{width}d}'
        _add_port(conn, template_id, name)


def seed_templates(conn):
    """导入种子设备模板（端口名 = 完整接口名，槽位写在名字里）"""
    # ---- S7503X-G 核心交换机 ----
    conn.execute(
        'INSERT OR IGNORE INTO device_templates (model, vendor, type, description) VALUES (?,?,?,?)',
        ('S7503X-G', 'H3C', 'network', '核心交换机'))
    s7503 = conn.execute("SELECT id FROM device_templates WHERE model='S7503X-G'").fetchone()[0]
    _add_port(conn, s7503, 'Slot0_Cu_MGMT')
    _add_ports_range(conn, s7503, 'Slot2_Fi_10GE_', 1, 48)
    _add_ports_range(conn, s7503, 'Slot3_Fi_40GE_', 1, 4)
    _add_ports_range(conn, s7503, 'Slot3_Fi_100GE_', 5, 12)
    _add_ports_range(conn, s7503, 'Slot3_Fi_40GE_', 13, 16)

    # ---- S6805-56HF-G 汇聚/接入交换机 ----
    conn.execute(
        'INSERT OR IGNORE INTO device_templates (model, vendor, type, description) VALUES (?,?,?,?)',
        ('S6805-56HF-G', 'H3C', 'network', '汇聚/接入交换机'))
    s6805 = conn.execute("SELECT id FROM device_templates WHERE model='S6805-56HF-G'").fetchone()[0]
    _add_port(conn, s6805, 'Cu_MGMT')
    _add_ports_range(conn, s6805, 'Fi_10GE_', 1, 48)
    _add_ports_range(conn, s6805, 'Fi_100GE_', 49, 56)

    # ---- S5130S-28T4X-EI-Q-G 接入交换机 ----
    conn.execute(
        'INSERT OR IGNORE INTO device_templates (model, vendor, type, description) VALUES (?,?,?,?)',
        ('S5130S-28T4X-EI-Q-G', 'H3C', 'network', '接入交换机'))
    s5130 = conn.execute("SELECT id FROM device_templates WHERE model='S5130S-28T4X-EI-Q-G'").fetchone()[0]
    _add_port(conn, s5130, 'Cu_MGMT')
    _add_ports_range(conn, s5130, 'Cu_GE_', 1, 28)
    _add_ports_range(conn, s5130, 'Fi_10GE_', 29, 32)

    # ---- 示例服务器模板（用户可删改）----
    conn.execute(
        'INSERT OR IGNORE INTO device_templates (model, vendor, type, description) VALUES (?,?,?,?)',
        ('五舟服务器-计算节点', '', 'server', '示例服务器模板，端口可删改'))
    server = conn.execute("SELECT id FROM device_templates WHERE model='五舟服务器-计算节点'").fetchone()[0]
    _add_ports_range(conn, server, 'NIC', 1, 15)
    _add_port(conn, server, 'BMC')
    _add_port(conn, server, 'iBMC')


def seed_dicts(conn):
    """导入全局选项字典种子"""
    seeds = [
        ('interface_status', 'Down'), ('interface_status', 'UP'),
        ('aggregation_mode', 'Dynamic'), ('aggregation_mode', 'Static'), ('aggregation_mode', '/'),
        ('interface_mode', 'Trunk'), ('interface_mode', 'Access'),
        ('interface_mode', 'Route'), ('interface_mode', 'IRF'), ('interface_mode', '/'),
    ]
    for i, (cat, val) in enumerate(seeds):
        conn.execute(
            'INSERT OR IGNORE INTO option_dicts (category, value, sort_order) VALUES (?,?,?)',
            (cat, val, i))


def _migrate_template_type(conn):
    """类型分类迁移（旧版 框式/盒式/服务器 -> 网络设备/服务器/其它设备）：
    重建 device_templates 表移除 CHECK 约束，旧值 chassis/fixed 映射为 network。
    幂等：仅当旧表仍带 CHECK 约束时执行。
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='device_templates'").fetchone()
    if not row or 'CHECK(type IN' not in (row[0] or ''):
        return False
    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        conn.executescript('''
            CREATE TABLE device_templates_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT UNIQUE NOT NULL,
                vendor TEXT,
                type TEXT,
                description TEXT
            );
            INSERT INTO device_templates_new (id, model, vendor, type, description)
                SELECT id, model, vendor,
                       CASE WHEN type IN ('chassis', 'fixed') THEN 'network' ELSE type END,
                       description
                FROM device_templates;
            DROP TABLE device_templates;
            ALTER TABLE device_templates_new RENAME TO device_templates;
        ''')
    finally:
        conn.execute('PRAGMA foreign_keys = ON')
    return True


def _migrate_merge_slot_prefix(conn):
    """槽位概念取消：把模板端口的槽位前缀合并进端口名（Slot2 + Fi_10GE_01 -> Slot2_Fi_10GE_01）。
    幂等：端口名已带 Slot 前缀的不再处理；slot_templates 已不存在则跳过。
    """
    has_slots = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='slot_templates'").fetchone()
    if not has_slots:
        return False
    cur = conn.execute('''
        UPDATE port_templates SET
            port_name = (SELECT s.slot_number FROM slot_templates s
                         WHERE s.id = port_templates.slot_template_id) || '_' || port_name,
            slot_template_id = NULL
        WHERE slot_template_id IS NOT NULL
          AND port_name NOT GLOB 'Slot[0-9]*_*' ''')
    return cur.rowcount > 0


def _migrate_drop_port_fields(conn):
    """v3 简化：端口只保留名称，删除 槽位/端口类型/速率/介质 字段及 slot_templates 表。
    幂等：port_templates 已无 port_type 列则跳过。
    """
    cols = {r[1] for r in conn.execute('PRAGMA table_info(port_templates)')}
    if 'port_type' not in cols:
        return False
    conn.commit()  # 提交未决事务，否则 PRAGMA foreign_keys 在事务内无效
    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        conn.executescript('''
            DROP TABLE IF EXISTS port_templates_new;
            DROP TABLE IF EXISTS project_ports_new;
            DROP TABLE IF EXISTS slot_templates;
            CREATE TABLE port_templates_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_template_id INTEGER NOT NULL,
                port_name TEXT NOT NULL,
                FOREIGN KEY (device_template_id) REFERENCES device_templates(id) ON DELETE CASCADE,
                UNIQUE(device_template_id, port_name)
            );
            INSERT INTO port_templates_new (id, device_template_id, port_name)
                SELECT id, device_template_id, port_name FROM port_templates;
            DROP TABLE port_templates;
            ALTER TABLE port_templates_new RENAME TO port_templates;
            CREATE TABLE project_ports_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_device_id INTEGER NOT NULL,
                template_port_id INTEGER,
                port_name TEXT NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                interface_status TEXT DEFAULT 'Down',
                FOREIGN KEY (project_device_id) REFERENCES project_devices(id) ON DELETE CASCADE,
                FOREIGN KEY (template_port_id) REFERENCES port_templates(id)
            );
            INSERT INTO project_ports_new (id, project_device_id, template_port_id, port_name, is_used, interface_status)
                SELECT id, project_device_id, template_port_id, port_name, is_used, interface_status FROM project_ports;
            DROP TABLE project_ports;
            ALTER TABLE project_ports_new RENAME TO project_ports;
        ''')
    finally:
        conn.execute('PRAGMA foreign_keys = ON')
    return True


def _migrate_drop_device_role(conn):
    """设备角色删除：清空 device_role 字典，重建 project_devices 去掉 role 列。幂等。"""
    conn.execute("DELETE FROM option_dicts WHERE category = 'device_role'")
    cols = {r[1] for r in conn.execute('PRAGMA table_info(project_devices)')}
    if 'role' not in cols:
        return False
    conn.commit()  # 提交未决事务，否则 PRAGMA foreign_keys 在事务内无效
    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        conn.executescript('''
            CREATE TABLE project_devices_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                template_id INTEGER,
                name TEXT NOT NULL,
                location TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (template_id) REFERENCES device_templates(id)
            );
            INSERT INTO project_devices_new (id, project_id, template_id, name, location)
                SELECT id, project_id, template_id, name, location FROM project_devices;
            DROP TABLE project_devices;
            ALTER TABLE project_devices_new RENAME TO project_devices;
        ''')
    finally:
        conn.execute('PRAGMA foreign_keys = ON')
    return True


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    # 只在数据库首次创建时导入种子数据；之后以用户数据为准
    # （用户删除的模板/字典值不会被每次启动种回来）
    is_new = not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        conn.executescript(SCHEMA)
        if _migrate_template_type(conn):
            print('已迁移模板类型分类（框式/盒式 -> 网络设备）')
        if _migrate_merge_slot_prefix(conn):
            print('已迁移槽位合并进端口名（槽位概念取消）')
        if _migrate_drop_port_fields(conn):
            print('已删除端口附加字段（槽位/类型/速率/介质）')
        if _migrate_drop_device_role(conn):
            print('已删除设备角色字段')
        if is_new:
            seed_templates(conn)
            seed_dicts(conn)
        conn.commit()
        # 输出统计信息
        for row in conn.execute('''
            SELECT t.model, t.type, COUNT(p.id) AS port_count
            FROM device_templates t LEFT JOIN port_templates p ON p.device_template_id = t.id
            GROUP BY t.id ORDER BY t.id'''):
            print(f'模板: {row["model"]} ({row["type"]}) 端口数: {row["port_count"]}')
        for row in conn.execute('SELECT category, COUNT(*) AS n FROM option_dicts GROUP BY category'):
            print(f'字典: {row["category"]} 共 {row["n"]} 项')
        print(f'数据库初始化完成: {DB_PATH}')
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
