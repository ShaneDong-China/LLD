# -*- coding: utf-8 -*-
"""连接管理：Cable 模型（一条物理链路一行，port_a < port_b 规范化存储）

一条连接保存后，从任一设备视角都能查到（查询/状态/导出天然双向），
不再需要"反向记录"——这正是对原需求"自动反向生成"的模型级实现。
"""
import re
from contextlib import closing

from .db_utils import get_conn, query_all, query_one, execute
from .project_utils import (port_display_name, add_dict_value, add_project_vlan,
                            update_interface_status, get_device_ports)


_CONN_JOIN = '''
    SELECT c.*,
           da.id AS device_a_id, da.name AS device_a_name,
           pa.id AS port_a_id, pa.port_name AS port_a_name, pa.interface_status AS port_a_status,
           db.id AS device_b_id, db.name AS device_b_name,
           pb.id AS port_b_id, pb.port_name AS port_b_name, pb.interface_status AS port_b_status
    FROM project_connections c
    JOIN project_ports pa ON pa.id = c.port_a_id
    JOIN project_ports pb ON pb.id = c.port_b_id
    JOIN project_devices da ON da.id = pa.project_device_id
    JOIN project_devices db ON db.id = pb.project_device_id
'''


# 连接行的接口显示名（端口名即完整接口名）
def conn_port_a_display(c):
    return c['port_a_name']


def conn_port_b_display(c):
    return c['port_b_name']


def get_connections(project_id):
    """项目全部连接（按 id 倒序）"""
    return query_all(_CONN_JOIN + ' WHERE c.project_id = ? ORDER BY c.id DESC', (project_id,))


def get_connection(connection_id):
    return query_one(_CONN_JOIN + ' WHERE c.id = ?', (connection_id,))


def get_connection_by_port(port_id):
    """包含指定端口的连接（查询页用）"""
    return query_one(
        _CONN_JOIN + ' WHERE c.port_a_id = ? OR c.port_b_id = ? LIMIT 1', (port_id, port_id))


def _port_basic(port_id):
    """端口基础信息（设备 id/名）"""
    return query_one('''
        SELECT pp.id, pp.project_device_id, pp.port_name, pp.is_used, pp.interface_status,
               d.project_id, d.name AS device_name
        FROM project_ports pp JOIN project_devices d ON d.id = pp.project_device_id
        WHERE pp.id = ?''', (port_id,))


def save_connection(project_id, local_port_id, remote_port_id, agg_local='', agg_remote='',
                    agg_mode_local='', agg_mode_remote='',
                    if_mode_local='', if_mode_remote='',
                    vlan_local='', vlan_remote='',
                    desc_local='', desc_remote='', note_local='', note_remote=''):
    """保存一条连接。返回 (connection_id, 新增字典值列表)

    校验：端口存在且属于本项目、对端设备与本地不同、两端均未占用、链路不重复。
    聚合组/聚合模式/接口模式/VLAN/描述/备注均按端保存：本端值写到本地端口所在端，对端值写到对端。
    """
    local = _port_basic(local_port_id)
    remote = _port_basic(remote_port_id)
    if not local or local['project_id'] != project_id:
        raise ValueError('本地端口无效或不属于当前项目')
    if not remote or remote['project_id'] != project_id:
        raise ValueError('对端端口无效或不属于当前项目')
    if local['project_device_id'] == remote['project_device_id']:
        raise ValueError('对端设备不能与本地设备相同（本端为同一设备）')
    if local['is_used']:
        raise ValueError(f'端口 {local["device_name"]}/{local["port_name"]} 已被占用')
    if remote['is_used']:
        raise ValueError(f'端口 {remote["device_name"]}/{remote["port_name"]} 已被占用')

    # a < b 规范化（使链路对唯一）
    port_a, port_b = sorted((local_port_id, remote_port_id))
    if port_a == local_port_id:
        agg_a, agg_b = agg_local, agg_remote
        agg_mode_a, agg_mode_b = agg_mode_local, agg_mode_remote
        if_mode_a, if_mode_b = if_mode_local, if_mode_remote
        vlan_a, vlan_b = vlan_local, vlan_remote
        desc_a, desc_b = desc_local, desc_remote
        note_a, note_b = note_local, note_remote
    else:
        agg_a, agg_b = agg_remote, agg_local
        agg_mode_a, agg_mode_b = agg_mode_remote, agg_mode_local
        if_mode_a, if_mode_b = if_mode_remote, if_mode_local
        vlan_a, vlan_b = vlan_remote, vlan_local
        desc_a, desc_b = desc_remote, desc_local
        note_a, note_b = note_remote, note_local

    if query_one('SELECT id FROM project_connections WHERE port_a_id=? AND port_b_id=?',
                 (port_a, port_b)):
        raise ValueError('该链路已存在，请勿重复保存')

    # 界面下拉之外的自定义值自动加入全局字典（两端值都做；'/' 表示无，不进字典）
    added = []
    for cat, val in (('aggregation_mode', agg_mode_local), ('aggregation_mode', agg_mode_remote),
                     ('interface_mode', if_mode_local), ('interface_mode', if_mode_remote)):
        if val and val != '/' and add_dict_value(cat, val):
            added.append(f'{cat}: {val}')

    with closing(get_conn()) as conn, conn:
        cur = conn.execute('''
            INSERT INTO project_connections
                (project_id, port_a_id, port_b_id, aggregation_group_a, aggregation_group_b,
                 aggregation_mode_a, aggregation_mode_b,
                 interface_mode_a, interface_mode_b,
                 vlan_id_a, vlan_id_b,
                 description_a, description_b, note_a, note_b)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (project_id, port_a, port_b, agg_a or None, agg_b or None,
             agg_mode_a or None, agg_mode_b or None,
             if_mode_a or None, if_mode_b or None,
             vlan_a or None, vlan_b or None,
             desc_a or None, desc_b or None, note_a or None, note_b or None))
        conn.execute('UPDATE project_ports SET is_used = 1 WHERE id IN (?,?)', (port_a, port_b))
        return cur.lastrowid, added


def delete_connection(connection_id):
    """删除连接并释放两端端口"""
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            'SELECT port_a_id, port_b_id FROM project_connections WHERE id = ?', (connection_id,)).fetchone()
        if not row:
            return
        conn.execute('DELETE FROM project_connections WHERE id = ?', (connection_id,))
        conn.execute('UPDATE project_ports SET is_used = 0 WHERE id IN (?,?)',
                     (row['port_a_id'], row['port_b_id']))


def precheck_batch_rows(project_id, device_id, rows):
    """批量连线预检（只读，不写库）：逐行检查，返回错误列表。
    规则与 sync 一致：本端端口存在且未占用、对端端口存在且未占用、链路不重复；
    模板设备缺对端端口=笔误报错，自由设备缺端口=可按需创建不算错。
    预检通过后才允许调 sync_device_rows 批量保存（整批回滚的依据）。"""
    def _cell(v):
        if v is None or (isinstance(v, float) and v != v):
            return ''
        return str(v).strip()

    errors = []
    ports = get_device_ports(device_id)
    by_disp = {port_display_name(p): p for p in ports}
    for r in rows:
        disp = _cell(r.get('接口'))
        port = by_disp.get(disp)
        if port is None:
            errors.append(f'{disp}: 本端端口不存在')
            continue
        if port['is_used']:
            errors.append(f'{disp}: 本端端口已被占用')
            continue
        remote_dev = _cell(r.get('对端设备'))
        remote_port_raw = _cell(r.get('对端接口'))
        if not remote_dev or not remote_port_raw:
            errors.append(f'{disp}: 缺少对端设备/端口')
            continue
        dev = query_one('SELECT * FROM project_devices WHERE project_id=? AND name=?',
                        (project_id, remote_dev))
        if dev is None:
            continue  # 未知设备：将按自由设备创建，可连线
        p = query_one('SELECT id, is_used FROM project_ports WHERE project_device_id=? AND port_name=?',
                      (dev['id'], remote_port_raw))
        if p is None:
            if dev['template_id'] is not None:
                errors.append(f'{disp}: 对端 {remote_dev}/{remote_port_raw} 不存在于该设备（请检查拼写）')
            continue  # 自由设备缺端口：按需创建，可连线
        if p['is_used']:
            errors.append(f'{disp}: 对端 {remote_dev}/{remote_port_raw} 已被占用')
            continue
        a, b = sorted((port['id'], p['id']))
        if query_one('SELECT id FROM project_connections WHERE port_a_id=? AND port_b_id=?', (a, b)):
            errors.append(f'{disp}: 与 {remote_dev}/{remote_port_raw} 的链路已存在')
    return errors


# ================= 设备视角网格同步（Excel 式批量编辑） =================

def _resolve_remote_port(project_id, dev_name, port_name_raw):
    """解析对端端口：
    - 项目内设备 + 精确端口名 -> 返回端口 id
    - 项目内模板设备 + 找不到端口 -> 返回 None（调用方报错）
    - 项目内自由设备 / 新设备 -> 按需创建自由端口
    """
    name = port_name_raw.strip()  # 端口名 = 完整接口名，原样查找
    dev = query_one('SELECT * FROM project_devices WHERE project_id=? AND name=?',
                    (project_id, dev_name))
    if dev:
        p = query_one('SELECT id FROM project_ports WHERE project_device_id=? AND port_name=?',
                      (dev['id'], name))
        if p:
            return p['id']
        if dev['template_id'] is not None:
            return None  # 模板设备上找不到该端口，视为笔误
        return execute('INSERT INTO project_ports (project_device_id, port_name) VALUES (?,?)',
                       (dev['id'], name))
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            'INSERT INTO project_devices (project_id, template_id, name) VALUES (?,?,?)',
            (project_id, None, dev_name))
        dev_id = cur.lastrowid
        cur = conn.execute(
            'INSERT INTO project_ports (project_device_id, port_name) VALUES (?,?)',
            (dev_id, name))
        return cur.lastrowid


def _update_connection_fields(conn_id, local_port_id, agg_local, agg_remote,
                              agg_mode_local, agg_mode_remote,
                              if_mode_local, if_mode_remote,
                              vlan_local, vlan_remote,
                              desc_local, desc_remote, note_local, note_remote):
    """更新连接字段（聚合组/聚合模式/接口模式/VLAN/描述/备注均按端口所在端写入）"""
    row = query_one('SELECT * FROM project_connections WHERE id=?', (conn_id,))
    if row['port_a_id'] == local_port_id:
        agg_a, agg_b = agg_local or None, agg_remote or None
        agg_mode_a, agg_mode_b = agg_mode_local or None, agg_mode_remote or None
        if_mode_a, if_mode_b = if_mode_local or None, if_mode_remote or None
        vlan_a, vlan_b = vlan_local or None, vlan_remote or None
        desc_a, desc_b = desc_local or None, desc_remote or None
        note_a, note_b = note_local or None, note_remote or None
    else:
        agg_a, agg_b = agg_remote or None, agg_local or None
        agg_mode_a, agg_mode_b = agg_mode_remote or None, agg_mode_local or None
        if_mode_a, if_mode_b = if_mode_remote or None, if_mode_local or None
        vlan_a, vlan_b = vlan_remote or None, vlan_local or None
        desc_a, desc_b = desc_remote or None, desc_local or None
        note_a, note_b = note_remote or None, note_local or None
    execute('''
        UPDATE project_connections SET aggregation_group_a=?, aggregation_group_b=?,
               aggregation_mode_a=?, aggregation_mode_b=?,
               interface_mode_a=?, interface_mode_b=?,
               vlan_id_a=?, vlan_id_b=?,
               description_a=?, description_b=?, note_a=?, note_b=?
        WHERE id=?''',
        (agg_a, agg_b, agg_mode_a, agg_mode_b, if_mode_a, if_mode_b,
         vlan_a, vlan_b, desc_a, desc_b, note_a, note_b, conn_id))


def sync_device_rows(project_id, device_id, rows):
    """按设备视角网格行批量同步连接（Excel 式编辑的保存引擎）。
    rows: [{'接口','接口状态','聚合组','聚合模式','聚合模式（对端）',
            '接口模式','接口模式（对端）','VLAN','VLAN（对端）',
            '对端设备','对端接口','描述','对端描述','备注','对端备注',
            '接口状态（对端）','聚合组（对端）'}, ...]
    规则：对端为空 -> 删除该端口连接；对端变化 -> 先删后建；对端不变 -> 更新字段。
    聚合模式/接口模式/VLAN/描述/备注均按端独立存储；描述留空时两端自动生成 To-xxx（备注不自动生成）；
    '/' 表示无，不进入全局/项目字典。
    返回 {created, updated, deleted, errors, dict_added, vlan_added}
    """
    created = updated = deleted = 0
    errors, dict_added, vlan_added = [], [], []
    ports = get_device_ports(device_id)
    by_disp = {port_display_name(p): p for p in ports}
    dev_row = query_one('SELECT name FROM project_devices WHERE id = ?', (device_id,))
    dev_name = dev_row['name'] if dev_row else ''  # 自动生成对端描述时用本端设备名

    def _cell(v):
        """网格单元格值清洗：None / NaN / 空白 -> 空字符串"""
        if v is None or (isinstance(v, float) and v != v):
            return ''
        return str(v).strip()

    for r in rows:
        disp = _cell(r.get('接口'))
        port = by_disp.get(disp)
        if port is None:
            continue  # 网格行无法对应端口（理论不会发生）
        try:
            # 1. 接口状态（含字典自动扩充；'/' 表示无，不进字典）
            st_val = _cell(r.get('接口状态'))
            if st_val:
                update_interface_status(port['id'], st_val)
                if st_val not in ('Down', 'UP') and st_val != '/' and add_dict_value('interface_status', st_val):
                    dict_added.append(f'接口状态:{st_val}')
            # 2. VLAN 自动进项目字典（本端+对端都进；'/' 表示无，跳过）
            for v in re.split(r'[\s,、]+', _cell(r.get('VLAN')) + ' ' + _cell(r.get('VLAN（对端）'))):
                if v and v != '/' and add_project_vlan(project_id, v):
                    vlan_added.append(v)

            remote_dev = _cell(r.get('对端设备'))
            remote_port_raw = _cell(r.get('对端接口'))
            existing = get_connection_by_port(port['id'])
            if not remote_dev or not remote_port_raw:
                if existing:
                    delete_connection(existing['id'])
                    deleted += 1
                continue

            if remote_dev == '＋自定义设备…':
                errors.append(f'{disp}: 请先填写自定义设备名称（在选择面板中）')
                continue

            remote_port_id = _resolve_remote_port(project_id, remote_dev, remote_port_raw)
            if remote_port_id is None:
                errors.append(f'{disp}: 对端端口 {remote_dev}/{remote_port_raw} 不存在于该设备，请检查拼写')
                continue

            agg_local = _cell(r.get('聚合组'))
            agg_remote = _cell(r.get('聚合组（对端）'))
            # 聚合模式/接口模式/VLAN 按端独立：本端值写本端、对端值写对端
            agg_mode_local = _cell(r.get('聚合模式'))
            agg_mode_remote = _cell(r.get('聚合模式（对端）'))
            if_mode_local = _cell(r.get('接口模式'))
            if_mode_remote = _cell(r.get('接口模式（对端）'))
            vlan_local = _cell(r.get('VLAN'))
            vlan_remote = _cell(r.get('VLAN（对端）'))
            # 描述/备注按端独立：本端值写本端、对端值写对端，互不影响（不再以改动侧为准）
            desc_local = _cell(r.get('描述'))
            desc_remote = _cell(r.get('对端描述'))
            note_local = _cell(r.get('备注'))
            note_remote = _cell(r.get('对端备注'))
            # 对端接口状态：与对端信息对称编辑，默认 UP（链路建立后对端应为活动状态）
            remote_status = _cell(r.get('接口状态（对端）')) or 'UP'

            def _do_create():
                nonlocal created
                rp = _port_basic(remote_port_id)
                if rp['is_used']:
                    errors.append(f'{disp}: 对端 {remote_dev}/{remote_port_raw} 已被占用')
                    return
                # 描述两端都自动生成（留空时）；备注不自动生成、按用户填写
                final_local = desc_local or f'To-{remote_dev}_{remote_port_raw}'
                final_remote = desc_remote or f'To-{dev_name}_{disp}'
                _, added = save_connection(project_id, port['id'], remote_port_id, agg_local, agg_remote,
                                           agg_mode_local, agg_mode_remote,
                                           if_mode_local, if_mode_remote,
                                           vlan_local, vlan_remote,
                                           final_local, final_remote, note_local, note_remote)
                update_interface_status(remote_port_id, remote_status)  # 对端接口状态写对端端口
                created += 1
                dict_added.extend(added)

            if not existing:
                _do_create()
            else:
                other_id = existing['port_b_id'] if existing['port_a_id'] == port['id'] else existing['port_a_id']
                if other_id == remote_port_id:
                    # 对端不变：更新字段（含对端聚合组/聚合模式/接口模式/VLAN/描述/备注与对端接口状态）
                    _update_connection_fields(existing['id'], port['id'], agg_local, agg_remote,
                                              agg_mode_local, agg_mode_remote,
                                              if_mode_local, if_mode_remote,
                                              vlan_local, vlan_remote,
                                              desc_local, desc_remote, note_local, note_remote)
                    update_interface_status(other_id, remote_status)
                    updated += 1
                else:
                    # 对端变化：先删后建
                    delete_connection(existing['id'])
                    deleted += 1
                    _do_create()
        except ValueError as e:
            errors.append(f'{disp}: {e}')

    return {'created': created, 'updated': updated, 'deleted': deleted,
            'errors': errors, 'dict_added': dict_added, 'vlan_added': vlan_added}
