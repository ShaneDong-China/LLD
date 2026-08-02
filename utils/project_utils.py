# -*- coding: utf-8 -*-
"""项目管理：项目 / 设备实例 / 端口克隆 / 端口状态"""
from contextlib import closing

from .db_utils import get_conn, query_all, query_one, execute
from .template_utils import get_template


def list_projects():
    """全部项目（含设备数、连接数）"""
    return query_all('''
        SELECT p.*,
               (SELECT COUNT(*) FROM project_devices d WHERE d.project_id = p.id) AS device_count,
               (SELECT COUNT(*) FROM project_connections c WHERE c.project_id = p.id) AS conn_count
        FROM projects p ORDER BY p.created_at DESC, p.id DESC''')


def get_project(project_id):
    return query_one('SELECT * FROM projects WHERE id = ?', (project_id,))


def _unique_project_name(name):
    """项目名重名时自动加后缀（XX、XX (2)、XX (3)...）"""
    if not query_one('SELECT id FROM projects WHERE name = ?', (name,)):
        return name
    i = 2
    while query_one('SELECT id FROM projects WHERE name = ?', (f'{name} ({i})',)):
        i += 1
    return f'{name} ({i})'


def create_project(name, description='', device_specs=None):
    """创建项目并克隆设备端口。
    device_specs: [(template_id, name, location), ...]
    返回 (project_id, 实际项目名)
    """
    device_specs = device_specs or []
    final_name = _unique_project_name(name)
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            'INSERT INTO projects (name, description) VALUES (?,?)', (final_name, description))
        project_id = cur.lastrowid
        for template_id, dev_name, location in device_specs:
            cur = conn.execute(
                'INSERT INTO project_devices (project_id, template_id, name, location) VALUES (?,?,?,?)',
                (project_id, template_id, dev_name, location))
            dev_id = cur.lastrowid
            # 克隆模板端口到设备实例（按模板顺序）
            if template_id is not None:
                conn.execute('''
                    INSERT INTO project_ports (project_device_id, template_port_id, port_name)
                    SELECT ?, id, port_name FROM port_templates
                    WHERE device_template_id = ? ORDER BY id''',
                    (dev_id, template_id))
    return project_id, final_name


def delete_project(project_id):
    """删除项目（设备/端口/连接/VLAN 全部级联删除）"""
    execute('DELETE FROM projects WHERE id = ?', (project_id,))


def get_project_devices(project_id):
    """项目内全部设备（含模板型号/类型）"""
    return query_all('''
        SELECT d.*, t.model, t.type AS template_type, t.vendor
        FROM project_devices d
        LEFT JOIN device_templates t ON t.id = d.template_id
        WHERE d.project_id = ? ORDER BY d.id''', (project_id,))


def add_project_device(project_id, template_id, name, location=''):
    """向已有项目添加设备并克隆端口，返回设备 id；设备名重复时抛 ValueError"""
    if query_one('SELECT id FROM project_devices WHERE project_id=? AND name=?',
                 (project_id, name)):
        raise ValueError(f'项目内已存在设备 "{name}"')
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            'INSERT INTO project_devices (project_id, template_id, name, location) VALUES (?,?,?,?)',
            (project_id, template_id, name, location))
        dev_id = cur.lastrowid
        if template_id is not None:
            conn.execute('''
                INSERT INTO project_ports (project_device_id, template_port_id, port_name)
                SELECT ?, id, port_name FROM port_templates
                WHERE device_template_id = ? ORDER BY id''',
                (dev_id, template_id))
    return dev_id


def delete_project_device(device_id):
    """删除项目设备：其连接一并删除、对端端口释放、端口级联删除"""
    with closing(get_conn()) as conn, conn:
        conn.execute('''
            DELETE FROM project_connections
            WHERE port_a_id IN (SELECT id FROM project_ports WHERE project_device_id = ?)
               OR port_b_id IN (SELECT id FROM project_ports WHERE project_device_id = ?)''',
            (device_id, device_id))
        # 重算剩余端口占用（被删连接的端口释放）
        conn.execute('''
            UPDATE project_ports SET is_used =
                EXISTS(SELECT 1 FROM project_connections c
                       WHERE c.port_a_id = project_ports.id OR c.port_b_id = project_ports.id)''')
        conn.execute('DELETE FROM project_devices WHERE id = ?', (device_id,))


def get_device_ports(device_id):
    """设备全部端口（端口名 = 完整接口名，按模板端口顺序 = 模板导入文件的顺序；
    自由端口排在最后）"""
    return query_all('''
        SELECT pp.* FROM project_ports pp
        WHERE pp.project_device_id = ?
        ORDER BY pp.template_port_id IS NULL, pp.template_port_id, pp.id''', (device_id,))


def get_device_port(device_id, port_name):
    """按端口名精确查找设备端口"""
    return query_one(
        'SELECT * FROM project_ports WHERE project_device_id = ? AND port_name = ?',
        (device_id, port_name))


def port_display_name(port):
    """接口显示名：端口名即完整接口名（Slot2_Fi_10GE_41 原样显示）"""
    return port['port_name'] if port else ''


def get_device_stats(device_id):
    """设备端口统计：总数 / 已占用数"""
    total = query_one(
        'SELECT COUNT(*) AS n FROM project_ports WHERE project_device_id = ?', (device_id,))
    used = query_one(
        'SELECT COUNT(*) AS n FROM project_ports WHERE project_device_id = ? AND is_used = 1',
        (device_id,))
    return (total['n'] if total else 0), (used['n'] if used else 0)


def update_interface_status(port_id, status):
    """更新端口接口状态（值来自全局接口状态字典）"""
    execute('UPDATE project_ports SET interface_status = ? WHERE id = ?', (status, port_id))


def get_device_port_by_id(port_id):
    """按 id 查端口，用于生成对端显示名"""
    return query_one('SELECT * FROM project_ports WHERE id = ?', (port_id,))


def get_or_create_free_port(project_id, device_name, port_name):
    """按需创建自由端口：对端设备不存在则先创建自由设备（无模板），端口按名创建。
    返回端口 id。用于连接录入时的自定义对端输入。"""
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            'SELECT id FROM project_devices WHERE project_id = ? AND name = ?',
            (project_id, device_name)).fetchone()
        if row:
            dev_id = row['id']
            p = conn.execute(
                'SELECT id FROM project_ports WHERE project_device_id = ? AND port_name = ?',
                (dev_id, port_name)).fetchone()
            if p:
                return p['id']
            cur = conn.execute(
                'INSERT INTO project_ports (project_device_id, port_name) VALUES (?,?)',
                (dev_id, port_name))
            return cur.lastrowid
        cur = conn.execute(
            'INSERT INTO project_devices (project_id, template_id, name) VALUES (?,?,?)',
            (project_id, None, device_name))
        dev_id = cur.lastrowid
        cur = conn.execute(
            'INSERT INTO project_ports (project_device_id, port_name) VALUES (?,?)',
            (dev_id, port_name))
        return cur.lastrowid


# ---------------- 全局选项字典 ----------------

def list_dict(category):
    return query_all(
        'SELECT * FROM option_dicts WHERE category = ? ORDER BY sort_order, id', (category,))


def add_dict_value(category, value):
    """向字典添加值（已存在则忽略），返回是否新增"""
    existed = query_one('SELECT id FROM option_dicts WHERE category=? AND value=?', (category, value))
    if existed:
        return False
    max_order = query_one(
        'SELECT MAX(sort_order) AS m FROM option_dicts WHERE category = ?', (category,))
    execute('INSERT INTO option_dicts (category, value, sort_order) VALUES (?,?,?)',
            (category, value, (max_order['m'] + 1) if max_order and max_order['m'] is not None else 0))
    return True


def delete_dict_value(category, value):
    execute('DELETE FROM option_dicts WHERE category = ? AND value = ?', (category, value))


# ---------------- 项目级 VLAN 字典 ----------------

def list_project_vlans(project_id):
    return query_all(
        'SELECT * FROM project_vlans WHERE project_id = ? ORDER BY sort_order, value', (project_id,))


def add_project_vlan(project_id, value, name=''):
    """添加项目 VLAN（已存在则忽略），返回是否新增"""
    existed = query_one(
        'SELECT id FROM project_vlans WHERE project_id=? AND value=?', (project_id, value))
    if existed:
        return False
    max_order = query_one(
        'SELECT MAX(sort_order) AS m FROM project_vlans WHERE project_id = ?', (project_id,))
    execute('INSERT INTO project_vlans (project_id, value, name, sort_order) VALUES (?,?,?,?)',
            (project_id, value, name,
             (max_order['m'] + 1) if max_order and max_order['m'] is not None else 0))
    return True


def delete_project_vlan(vlan_id):
    execute('DELETE FROM project_vlans WHERE id = ?', (vlan_id,))
