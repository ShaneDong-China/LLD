# -*- coding: utf-8 -*-
"""设备模板管理：模板 / 端口的增删查（端口名 = 完整接口名）"""
from .db_utils import query_all, query_one, execute

# 模板类型显示名（类型由用户输入决定，程序不做推断）
TYPE_LABELS = {'network': '网络设备', 'server': '服务器', 'other': '其它设备'}


def type_label(t):
    return TYPE_LABELS.get(t, t or '')


def list_templates():
    """全部模板（含端口数量）"""
    return query_all('''
        SELECT t.*, (SELECT COUNT(*) FROM port_templates p WHERE p.device_template_id = t.id) AS port_count
        FROM device_templates t ORDER BY t.id''')


def get_template(template_id):
    return query_one('SELECT * FROM device_templates WHERE id = ?', (template_id,))


def get_template_by_model(model):
    return query_one('SELECT * FROM device_templates WHERE model = ?', (model,))


def create_template(model, vendor, type_, description=''):
    """新增模板，型号重复时抛出 ValueError"""
    if get_template_by_model(model):
        raise ValueError(f'型号 "{model}" 已存在')
    return execute(
        'INSERT INTO device_templates (model, vendor, type, description) VALUES (?,?,?,?)',
        (model, vendor, type_, description))


def delete_template(template_id):
    """删除模板（级联删槽位/端口）；被项目设备引用时拒绝"""
    used = query_one(
        'SELECT COUNT(*) AS n FROM project_devices WHERE template_id = ?', (template_id,))
    if used and used['n'] > 0:
        raise ValueError(f'该模板已被 {used["n"]} 个项目设备引用，无法删除')
    execute('DELETE FROM device_templates WHERE id = ?', (template_id,))


def update_template(template_id, model, vendor, type_, description=''):
    """更新模板基本信息；型号与其他模板重复时抛 ValueError"""
    if not get_template(template_id):
        raise ValueError('模板不存在')
    dup = query_one('SELECT id FROM device_templates WHERE model=? AND id != ?',
                    (model, template_id))
    if dup:
        raise ValueError(f'型号 "{model}" 已被其他模板使用')
    execute('UPDATE device_templates SET model=?, vendor=?, type=?, description=? WHERE id=?',
            (model, vendor, type_, description, template_id))


# ---------------- 端口 ----------------

def list_ports(template_id):
    """模板端口列表（端口名 = 完整接口名，严格按录入顺序 = 导入文件的顺序）"""
    return query_all(
        'SELECT * FROM port_templates WHERE device_template_id = ? ORDER BY id',
        (template_id,))


def add_port(template_id, port_name):
    """新增模板端口（端口名 = 完整接口名），同模板内端口名重复时抛出 ValueError"""
    if query_one('SELECT id FROM port_templates WHERE device_template_id=? AND port_name=?',
                 (template_id, port_name)):
        raise ValueError(f'端口 "{port_name}" 已存在')
    return execute(
        'INSERT INTO port_templates (device_template_id, port_name) VALUES (?,?)',
        (template_id, port_name))


def delete_port(port_id):
    """删除端口；被项目设备端口引用时拒绝"""
    used = query_one(
        'SELECT COUNT(*) AS n FROM project_ports WHERE template_port_id = ?', (port_id,))
    if used and used['n'] > 0:
        raise ValueError(f'该端口已被 {used["n"]} 个项目设备端口使用，无法删除')
    execute('DELETE FROM port_templates WHERE id = ?', (port_id,))


def update_port(port_id, port_name):
    """更新端口名（端口名 = 完整接口名）；同模板内端口名重复时抛 ValueError"""
    port = query_one('SELECT * FROM port_templates WHERE id = ?', (port_id,))
    if not port:
        raise ValueError('端口不存在')
    dup = query_one('SELECT id FROM port_templates WHERE device_template_id=? AND port_name=? AND id != ?',
                    (port['device_template_id'], port_name, port_id))
    if dup:
        raise ValueError(f'端口 "{port_name}" 已存在')
    execute('UPDATE port_templates SET port_name=? WHERE id=?', (port_name, port_id))
