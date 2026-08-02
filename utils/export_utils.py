# -*- coding: utf-8 -*-
"""Excel 导出：每台设备一个 sheet 的 Port_Design 格式（LLD 交付物）

服务器模板设备（type=server）自动汇总到一张「服务器」sheet，
用「设备」列区分，不再每台服务器一个 sheet。
"""
import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .project_utils import get_project, get_project_devices, get_device_ports, port_display_name
from .connection_utils import get_connections, conn_port_a_display, conn_port_b_display

HEADERS = ['设备', '位置', '接口', '接口状态', '聚合组', '聚合模式', '接口模式', 'VLAN', '对端设备', '对端接口', '连接描述', '备注']
WIDTHS = [16, 14, 24, 10, 12, 11, 11, 14, 16, 24, 34, 16]
SERVER_SHEET = '服务器'


def _safe_sheet_name(name):
    """Excel sheet 名不允许的字符替换为下划线，且不超过 31 字符"""
    name = re.sub(r'[\[\]:*?/\\]', '_', str(name))
    return name[:31]


def _port_row(dev, p, conn_by_port):
    """一行端口数据（Port_Design 行，含设备名/位置列）"""
    disp = port_display_name(p)
    loc = dev['location'] or ''
    conn = conn_by_port.get(p['id'])
    if conn:
        # 本端聚合组：取连接中属于本设备那端的聚合组
        if conn['port_a_id'] == p['id']:
            agg = conn['aggregation_group_a'] or ''
            remote_dev, remote_port = conn['device_b_name'], conn_port_b_display(conn)
        else:
            agg = conn['aggregation_group_b'] or ''
            remote_dev, remote_port = conn['device_a_name'], conn_port_a_display(conn)
        return [dev['name'], loc, disp, p['interface_status'] or '', agg,
                conn['aggregation_mode'] or '', conn['interface_mode'] or '',
                conn['vlan_id'] or '', remote_dev, remote_port,
                conn['description'] or '', conn['note'] or '']
    return [dev['name'], loc, disp, p['interface_status'] or '', '', '', '', '', '', '', '', '']


def _write_device_sheet(wb, dev, conn_by_port):
    """单台设备的 Port_Design sheet"""
    model = dev['model'] or ''
    ws = wb.create_sheet(_safe_sheet_name(dev['name']))
    ws.append([f"{dev['name']} - Port_Design {model}".rstrip()])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append(HEADERS)
    for cell in ws[2]:
        cell.font = Font(bold=True)
    for p in get_device_ports(dev['id']):
        ws.append(_port_row(dev, p, conn_by_port))
    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def export_project(project_id):
    """导出项目为 Port_Design Excel，返回 BytesIO。
    服务器模板设备自动汇总到一张「服务器」sheet（用设备列区分）；
    自由设备（无模板）不生成独立 sheet，只出现在对端列。
    """
    devices = get_project_devices(project_id)
    conns = get_connections(project_id)
    # 端口 id -> 连接（一条链路两端都可索引）
    conn_by_port = {}
    for c in conns:
        conn_by_port[c['port_a_id']] = c
        conn_by_port[c['port_b_id']] = c

    wb = Workbook()
    wb.remove(wb.active)  # 删除默认空白 sheet

    servers = []
    for dev in devices:
        if dev['template_id'] is None:
            continue  # 自由设备不生成 sheet，只出现在对端列
        if dev.get('template_type') == 'server':
            servers.append(dev)
            continue
        _write_device_sheet(wb, dev, conn_by_port)

    # ---- 服务器汇总 sheet（一台服务器都不再单独成表） ----
    if servers:
        ws = wb.create_sheet(SERVER_SHEET)
        ws.append([f'{SERVER_SHEET} - Port_Design'])
        ws['A1'].font = Font(bold=True, size=13)
        ws.append(HEADERS)
        for cell in ws[2]:
            cell.font = Font(bold=True)
        for dev in servers:
            for p in get_device_ports(dev['id']):
                ws.append(_port_row(dev, p, conn_by_port))
        for i, w in enumerate(WIDTHS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # 项目无任何设备时，至少生成一个提示 sheet（openpyxl 不允许保存无 sheet 的工作簿）
    if not wb.sheetnames:
        ws = wb.create_sheet('项目为空')
        ws.append(['该项目暂无设备，无法导出端口数据'])
        ws['A1'].font = Font(bold=True)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def export_filename(project_id):
    """导出文件名 = 项目名_Port_Design.xlsx"""
    project = get_project(project_id)
    return f"{project['name']}_Port_Design.xlsx" if project else 'Port_Design.xlsx'
