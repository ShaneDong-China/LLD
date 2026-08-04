# -*- coding: utf-8 -*-
"""项目详情（设备平铺选择 + 筛选 + 单击行高亮 + 编辑弹窗）

不显示在侧边栏，只能从「项目管理 → 进入」打开。
交互流程：顶部选择设备卡片 -> 筛选（仅显示UP/显示All）-> 单击行高亮选中
-> 「✏️ 编辑所选行」弹窗中填写对端设备/端口/参数 -> 保存即生效。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import pandas as pd
import streamlit as st
from utils import project_utils as pu
from utils import connection_utils as cu
from utils import export_utils as eu
from utils.ui_utils import apply_layout


def flash_msg():
    msg = st.session_state.pop('flash', None)
    if msg:
        kind, text = msg
        (st.success if kind == 'success' else st.error if kind == 'error' else st.info)(text)


st.set_page_config(page_title='项目详情', page_icon='📂', layout='wide')
apply_layout()

# ---------------- 读取项目 ----------------
# 优先级: URL 参数 -> 会话中最近打开的项目 -> 项目选择器
pid = st.query_params.get('project_id')
try:
    pid = pid[0] if isinstance(pid, list) else pid
    project_id = int(pid)
except (TypeError, ValueError):
    project_id = None
if project_id is None:
    project_id = st.session_state.get('current_project_id')

project = pu.get_project(project_id) if project_id else None
if not project:
    st.title('📂 项目详情')
    projects = pu.list_projects()
    if not projects:
        st.info('还没有项目，请先到「项目管理」页面创建或导入项目。')
        st.stop()
    st.caption('请选择要查看的项目（与项目管理页一致）：')
    for p in projects:
        with st.container(border=True):
            cols = st.columns([2.2, 1.4, 1, 1, 1.2])
            cols[0].markdown(f"**{p['name']}**")
            cols[1].write(p['created_at'][:19])
            cols[2].write(f"{p['device_count']} 台设备")
            cols[3].write(f"{p['conn_count']} 条连接")
            if cols[4].button('进入', key=f'pick_{p["id"]}', width='stretch'):
                st.session_state['current_project_id'] = p['id']
                st.query_params['project_id'] = str(p['id'])
                st.rerun()
    st.stop()

# 项目名：内联样式直接控制大小（不依赖 Streamlit 标题组件的 DOM 结构）
import html as _html
st.markdown(
    f'<div style="font-size:1.5rem;font-weight:600;margin:0">📂 {_html.escape(project["name"])}</div>',
    unsafe_allow_html=True)
flash_msg()
if project['description']:
    st.caption(project['description'])

devices = pu.get_project_devices(project['id'])
dev_name_map = {d['id']: d['name'] for d in devices}


# ---------------- 顶部按钮区 ----------------
top = st.columns([1, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
if top[0].button('← 返回项目列表', width='stretch'):
    st.switch_page('views/项目管理.py')


@st.dialog('添加设备', width='large')
def add_device_dialog():
    """表格批量添加（fixed 模式，验证下拉是否不闪）：每行一台设备（模板下拉 + 名称/位置/IP），
    默认 100 行空行直接滚动填写；整批预检：已填行 名称空/重名/模板无效 → 全部不添加。"""
    from utils import template_utils as tu
    templates = tu.list_templates()
    if not templates:
        st.warning('模板库为空，请先到「模板管理」页面创建模板')
        return
    st.caption('每行一台设备：选模板、填名称/位置/IP（fixed 模式不刷新）；下拉第一项空白=清空模板')
    tpl_models = [t['model'] for t in templates]
    # 编辑数据：首次打开默认 100 行空行（模板列默认空；下拉首项空白可清空；非空即参与添加）
    if st.session_state.get('add_dev_data') is None:
        st.session_state['add_dev_data'] = pd.DataFrame(
            [{'模板': '', '设备名称': '', '位置/机架': '', '管理IP': '', 'BMC IP': ''}] * 100)

    edited = st.data_editor(
        st.session_state['add_dev_data'], key='add_dev_grid', num_rows='fixed',
        hide_index=True, width='stretch',
        height=40 + 35 * 10,  # 固定显示 10 行高度，行数超过后表格内滚动
        column_config={
            # 首项空白选项用于清空该行模板；非空白=已选择（参与添加）
            '模板': st.column_config.SelectboxColumn('模板', options=[''] + tpl_models),
        },
        # 注意：不设 on_change——设了每个字符编辑都会触发 rerun 刷新；
        # fixed 模式下编辑由 widget state 保留（批量编辑设备已验证）
    )
    st.session_state['add_dev_data'] = edited  # 兜底：非交互触发的 rerun（如点保存按钮）也同步

    def _cell(v):
        return '' if v is None or pd.isna(v) else str(v).strip()

    # 参与行 = 模板列非空（以模板列为准判断，不再看设备名称）；空行跳过
    filled = [(i, edited.iloc[i]) for i in range(len(edited))
              if _cell(edited.iloc[i]['模板'])]
    if st.button(f'添加设备（{len(filled)} 台）', type='primary'):
        # ---- 整批预检：先全部检查，任一行有问题则全部不添加 ----
        errors = []
        seen = set()
        existing = {d['name'] for d in pu.get_project_devices(project['id'])}
        tpl_by_model = {t['model']: t for t in templates}
        for i, r in filled:
            name = _cell(r['设备名称'])
            if not name:
                errors.append(f'第 {i + 1} 行：设备名称不能为空')
                continue
            if name in seen or name in existing:
                errors.append(f'第 {i + 1} 行：设备「{name}」已存在')
            seen.add(name)
            if _cell(r['模板']) not in tpl_by_model:
                errors.append(f'第 {i + 1} 行：模板「{_cell(r["模板"])}」无效')
        if errors:
            st.error(f'有 {len(errors)} 处问题，本次未添加（整批回滚）：')
            for e in errors[:8]:
                st.write(f'- {e}')
            return
        # ---- 预检全过，逐行添加 ----
        for i, r in filled:
            tpl = tpl_by_model[_cell(r['模板'])]
            pu.add_project_device(project['id'], tpl['id'], _cell(r['设备名称']),
                                  _cell(r['位置/机架']), _cell(r['管理IP']), _cell(r['BMC IP']))
        st.session_state.pop('add_dev_grid', None)
        st.session_state.pop('add_dev_data', None)
        st.session_state['flash'] = ('success', f'已添加 {len(filled)} 台设备，端口已克隆')
        st.rerun()


@st.dialog('📥 导出 Excel')
def export_dialog():
    bio = eu.export_project(project['id'])
    st.download_button(
        '下载 Excel', data=bio.getvalue(),
        file_name=eu.export_filename(project['id']),
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', width='stretch',
        on_click=lambda: st.session_state.update(close_export=True))
    if st.session_state.pop('close_export', False):  # 回调里不能 rerun，用标记在主体关闭
        st.rerun()


@st.dialog('📥 导出线缆标签', width='large')
def cable_label_export_dialog():
    """线缆标签（From/To 格式串，只含已连接线缆）。格式存 app_settings（下载时保存）。"""
    st.caption('每根线缆两端各一行（本端在 From），按设备排序——贴标签时一台一台过')
    fmt_cur = st.session_state.get('cable_fmt',
                                   pu.get_setting('cable_label_format', eu.DEFAULT_CABLE_FORMAT))
    fmt = st.text_input('线缆标签格式', value=fmt_cur, key='cable_fmt',
                        help='占位符：{位置} {设备} {接口}；空值自动去掉（如 H10-SW1-Fi_10GE_1）')
    preview = eu.cable_label_preview(project['id'], fmt)
    if preview:
        st.caption('预览（前 6 行，每根线缆 2 行）：')
        st.dataframe(pd.DataFrame(preview, columns=['From', 'To']), hide_index=True,
                     width='stretch', height=40 + 35 * len(preview))
    else:
        st.caption('项目暂无连接，线缆标签为空')
    st.download_button(
        '下载线缆标签', data=eu.export_cable_labels(project['id'], fmt).getvalue(),
        file_name=eu.cable_label_filename(project['id']),
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', width='stretch',
        on_click=lambda: (pu.set_setting('cable_label_format', fmt),
                          st.session_state.update(close_export=True)))
    if st.session_state.pop('close_export', False):  # 回调里不能 rerun，用标记在主体关闭
        st.rerun()


@st.dialog('📥 导出设备标签', width='large')
def device_label_export_dialog():
    """设备标签（全部设备，勾选列 + 列顺序可调）。设置存 app_settings（下载时保存）。
    顺序 = 勾选列列表顺序：勾选加入末尾、取消移除，下拉选列 + ⬆/⬇ 换位。"""
    st.caption('全部设备（含未连接）')
    col_keys = list(eu.DEVICE_LABEL_COLUMNS)
    # 当前有序勾选列：弹窗内交互优先（session），否则读存储，否则默认全列
    saved = pu.get_setting('device_label_columns')
    saved_cols = json.loads(saved) if saved else col_keys
    order = list(st.session_state.get('dlc_order', saved_cols))

    # ---- 勾选列（新勾选加末尾 / 取消移除，顺序保持） ----
    cols = st.columns(len(col_keys))
    for i, k in enumerate(col_keys):
        cur = st.session_state.get(f'dlc_{k}', k in order)
        checked = cols[i].checkbox(k, value=cur, key=f'dlc_{k}')
        if checked and k not in order:
            order.append(k)
        if not checked and k in order:
            order.remove(k)
    st.session_state['dlc_order'] = order

    # ---- 列顺序：下拉选列，上移/下移放下拉框下一行 ----
    if order:
        move_col = st.selectbox('调整列顺序', order, key='dlc_move_col')
        idx = order.index(move_col)
        c1, c2 = st.columns([1, 1])
        if c1.button('⬆ 上移', key='dlc_up', disabled=idx <= 0,
                     help='把选中的列往前移一位'):
            order[idx], order[idx - 1] = order[idx - 1], order[idx]
            st.session_state['dlc_order'] = order
        if c2.button('⬇ 下移', key='dlc_down', disabled=idx >= len(order) - 1,
                     help='把选中的列往后移一位'):
            order[idx], order[idx + 1] = order[idx + 1], order[idx]
            st.session_state['dlc_order'] = order

    # ---- 预览 + 下载 ----
    if not order:
        st.warning('至少勾选一列才能导出设备标签')
    else:
        dev_rows = []
        for d in pu.get_project_devices(project['id'])[:5]:
            dev_rows.append([d[eu.DEVICE_LABEL_COLUMNS[c]] or '' for c in order])
        if dev_rows:
            st.caption('预览（前 5 台）：')
            st.dataframe(pd.DataFrame(dev_rows, columns=order), hide_index=True,
                         width='stretch', height=40 + 35 * len(dev_rows))
        else:
            st.caption('项目暂无设备')
    st.download_button(
        '下载设备标签', data=eu.export_device_labels(project['id'], order).getvalue(),
        file_name=eu.device_label_filename(project['id']),
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', width='stretch', disabled=not order,
        on_click=lambda: (pu.set_setting('device_label_columns', json.dumps(order)),
                          st.session_state.update(close_export=True)))
    if st.session_state.pop('close_export', False):  # 回调里不能 rerun，用标记在主体关闭
        st.rerun()


@st.dialog('VLAN 设置（本项目）')
def vlan_dialog():
    vlans = pu.list_project_vlans(project['id'])
    if vlans:
        st.dataframe(
            [{'VLAN': v['value'], '名称': v['name'] or ''} for v in vlans],
            hide_index=True, width='stretch')
        del_v = st.selectbox('删除 VLAN', [v['value'] for v in vlans],
                             format_func=lambda v: f"{v}（{next((x['name'] for x in vlans if x['value'] == v), '') or ''}）".strip() or v)
        if st.button('删除所选'):
            target = next(v for v in vlans if v['value'] == del_v)
            pu.delete_project_vlan(target['id'])
            st.session_state['flash'] = ('success', f'VLAN {del_v} 已删除')
            st.rerun()
    else:
        st.caption('本项目还没有 VLAN，请在下方添加')
    st.divider()
    with st.form('add_vlan_form'):
        v = st.text_input('VLAN 值 :red[*]', placeholder='如 164')
        n = st.text_input('名称（选填）', placeholder='如 管理')
        if st.form_submit_button('添加 VLAN'):
            if not v.strip():
                st.error('VLAN 值不能为空')
            elif pu.add_project_vlan(project['id'], v.strip(), n.strip()):
                st.session_state['flash'] = ('success', f'VLAN {v.strip()} 已添加')
                st.rerun()
            else:
                st.warning(f'VLAN {v.strip()} 已存在')


@st.dialog('设备预览', width='large')
def template_preview_dialog():
    st.caption(f'共 {len(devices)} 台设备')
    st.dataframe(
        [{'设备': d['name'], '模板': d['model'] or '自由设备（无模板）',
          '位置': d['location'] or '-',
          '管理IP': d['management_ip'] or '-', 'BMC IP': d['bmc_ip'] or '-',
          '端口占用': f"{pu.get_device_stats(d['id'])[1]}/{pu.get_device_stats(d['id'])[0]}"}
         for d in devices],
        hide_index=True, width='stretch')


@st.dialog('✏️ 批量编辑设备', width='large')
def batch_edit_device_dialog():
    """全部设备一张表，双击单元格直接编辑（设备名称/位置/管理IP/BMC IP），
    点「保存修改」统一写库；模板/端口占用只读。"""
    devs = pu.get_project_devices(project['id'])
    if not devs:
        st.info('项目暂无设备')
        return
    st.caption('双击单元格直接修改，改完点「保存修改」（名称为空/重名的行会报错不保存）')
    rows = [{'设备名称': d['name'], '设备位置': d['location'] or '',
             '管理IP': d['management_ip'] or '', 'BMC IP': d['bmc_ip'] or '',
             '模板': d['model'] or '自由设备（无模板）',
             '端口占用': f"{pu.get_device_stats(d['id'])[1]}/{pu.get_device_stats(d['id'])[0]}"}
            for d in devs]

    def _cell(v):
        return '' if v is None or pd.isna(v) else str(v)

    df = pd.DataFrame(rows)
    edited = st.data_editor(df, key='de_dev_grid', num_rows='fixed',
                            disabled=['模板', '端口占用'], hide_index=True,
                            width='stretch', height=40 + 35 * min(len(devs), 14))
    # 对比编辑前后找出修改行（不依赖编辑事件，只看返回值差异）
    changed = []
    for i in range(len(devs)):
        if any(_cell(edited.iloc[i][c]) != _cell(rows[i][c])
               for c in ('设备名称', '设备位置', '管理IP', 'BMC IP')):
            changed.append(i)
    if st.button(f'💾 保存修改（{len(changed)} 台）', type='primary', disabled=not changed):
        errors, ok = [], 0
        for i in changed:
            dev = devs[i]
            name = _cell(edited.iloc[i]['设备名称']).strip()
            if not name:
                errors.append(f'设备「{dev["name"]}」名称不能为空')
                continue
            try:
                pu.update_project_device(
                    dev['id'], name,
                    _cell(edited.iloc[i]['设备位置']).strip(),
                    _cell(edited.iloc[i]['管理IP']).strip(),
                    _cell(edited.iloc[i]['BMC IP']).strip())
                ok += 1
            except ValueError as e:
                errors.append(str(e))
        if errors:
            st.error(f'保存 {ok} 台，失败 {len(errors)} 台：' + '；'.join(errors))
        else:
            st.success(f'已保存 {ok} 台设备')
            st.session_state.pop('de_dev_grid', None)  # 清编辑器状态，重读库刷新
            st.rerun()


@st.dialog('删除设备')
def delete_device_dialog(dev):
    st.warning(f"确定删除设备「{dev['name']}」？其全部端口与连接将一并删除（对端端口自动释放），且不可恢复。")
    if st.button('确认删除', type='primary'):
        pu.delete_project_device(dev['id'])
        st.session_state['flash'] = ('success', f"设备「{dev['name']}」已删除")
        st.rerun()


if top[1].button('➕ 添加设备', width='stretch'):
    add_device_dialog()
if top[2].button('📥 导出 Excel', width='stretch'):
    st.session_state.pop('close_export', None)
    export_dialog()
if top[3].button('📥 导出设备标签', width='stretch'):
    st.session_state.pop('close_export', None)
    device_label_export_dialog()
if top[4].button('📥 导出线缆标签', width='stretch'):
    st.session_state.pop('close_export', None)
    cable_label_export_dialog()
if top[5].button('VLAN 设置', width='stretch'):
    vlan_dialog()
if top[6].button('🔄 刷新', width='stretch'):
    st.rerun()

st.divider()


# ---------------- 网格数据（每次从数据库重建） ----------------
def _build_grid_df(dev_id):
    """某设备的端口网格（每端口一行）"""
    dev = next((d for d in devices if d['id'] == dev_id), None)
    dev_name = dev['name'] if dev else ''
    dev_location = dev['location'] or '' if dev else ''
    rows = []
    for p in pu.get_device_ports(dev_id):
        disp = pu.port_display_name(p)
        conn = cu.get_connection_by_port(p['id'])
        if conn:
            local_side = conn['port_a_id'] == p['id']
            rows.append({
                '本端设备': dev_name,
                '位置': dev_location,
                '接口': disp,
                '接口状态': p['interface_status'] or '',
                '聚合组': (conn['aggregation_group_a'] if local_side else conn['aggregation_group_b']) or '',
                # 聚合模式/接口模式/VLAN 按端：网格是本端视角，显示本端值
                '聚合模式': (conn['aggregation_mode_a'] if local_side else conn['aggregation_mode_b']) or '',
                '接口模式': (conn['interface_mode_a'] if local_side else conn['interface_mode_b']) or '',
                'VLAN': (conn['vlan_id_a'] if local_side else conn['vlan_id_b']) or '',
                '对端设备': conn['device_b_name'] if local_side else conn['device_a_name'],
                '对端接口': cu.conn_port_b_display(conn) if local_side else cu.conn_port_a_display(conn),
                # 描述/备注按端：网格是本端视角，显示本端值（与聚合组列一致）
                '描述': (conn['description_a'] if local_side else conn['description_b']) or '',
                '备注': (conn['note_a'] if local_side else conn['note_b']) or '',
            })
        else:
            rows.append({'本端设备': dev_name, '位置': dev_location, '接口': disp,
                         '接口状态': p['interface_status'] or '',
                         '聚合组': '', '聚合模式': '', '接口模式': '', 'VLAN': '',
                         '对端设备': '', '对端接口': '', '描述': '', '备注': ''})
    return pd.DataFrame(rows)


# ---------------- 编辑行弹窗 ----------------
def dict_field(label, category, current, key):
    """全局字典下拉（标准值，不提供自定义输入；存量字典外的值仍可显示）"""
    values = [v['value'] for v in pu.list_dict(category)]
    if current and current not in values:
        values.append(current)
    idx = values.index(current) if current in values else 0
    return st.selectbox(label, values, index=idx, key=key)


def vlan_multiselect(label, current, key, if_mode, vlans, vlan_opts):
    """VLAN 多选（空格分隔存储）；接口模式 Route 时默认显示 /（未选则存 /，可手动改）"""
    cur = [x for x in current.split() if x]
    opts = list(vlan_opts)
    for v in cur:
        if v not in opts:
            opts.append(v)  # 旧数据中字典外的值也允许保留选中
    is_route = str(if_mode).upper() == 'ROUTE'
    sel = st.multiselect(
        label, opts, default=cur, key=key,
        format_func=lambda v: (f"{v}（{next((x['name'] for x in vlans if x['value'] == v), '')}）"
                               if any(x['value'] == v and x['name'] for x in vlans) else v),
        placeholder='/' if is_route else '选择 VLAN',
        help='多选，保存时以空格分隔（如 160 161）')
    return ' '.join(sel) or ('/' if is_route else '')


def _param_block(prefix, side, vlans, vlan_opts, default_status='UP', agg_placeholder='如 11'):
    """连接参数左右对称块（批量连线用）：接口状态/接口模式/VLAN/聚合模式/聚合组/描述/备注。
    prefix 用于 widget key 唯一；side 用于标签后缀（'' 本端 / '（对端）' 对端）。"""
    status_in = dict_field(f'接口状态{side}', 'interface_status', default_status, f'{prefix}_status')
    if_mode_in = dict_field(f'接口模式{side}', 'interface_mode', '', f'{prefix}_if_mode')
    vlan_in = vlan_multiselect(f'VLAN{side}', '', f'{prefix}_vlan', if_mode_in, vlans, vlan_opts)
    agg_mode_in = dict_field(f'聚合模式{side}', 'aggregation_mode', '', f'{prefix}_agg_mode')
    agg_in = st.text_input(f'聚合组{side}', key=f'{prefix}_agg',
                           value='/' if agg_mode_in == '/' else '',
                           placeholder=agg_placeholder if agg_mode_in != '/' else '不聚合')
    desc_in = st.text_input(f'连接描述{side}（留空自动生成）', key=f'{prefix}_desc')
    note_in = st.text_input(f'备注{side}', key=f'{prefix}_note', placeholder='选填')
    return status_in, if_mode_in, vlan_in, agg_mode_in, agg_in, desc_in, note_in


@st.dialog('✏️ 编辑行', width='large')
def edit_row_dialog(dev_id, row_index):
    """编辑设备某一行端口（row_index 为 get_device_ports 的下标）"""
    ports = pu.get_device_ports(dev_id)
    if row_index is None or row_index >= len(ports):
        st.error('行号无效，请重新选择')
        return
    port = ports[row_index]
    disp = pu.port_display_name(port)
    conn = cu.get_connection_by_port(port['id'])
    if conn:
        local_side = conn['port_a_id'] == port['id']
        cur_dev = conn['device_b_name'] if local_side else conn['device_a_name']
        cur_port = cu.conn_port_b_display(conn) if local_side else cu.conn_port_a_display(conn)
        other_id = conn['port_b_id'] if local_side else conn['port_a_id']
        agg_local = (conn['aggregation_group_a'] if local_side else conn['aggregation_group_b']) or ''
        # 聚合模式/接口模式/VLAN 按端独立读取：本端值 + 对端值
        agg_mode_local = (conn['aggregation_mode_a'] if local_side else conn['aggregation_mode_b']) or ''
        agg_mode_remote = (conn['aggregation_mode_b'] if local_side else conn['aggregation_mode_a']) or ''
        if_mode_local = (conn['interface_mode_a'] if local_side else conn['interface_mode_b']) or ''
        if_mode_remote = (conn['interface_mode_b'] if local_side else conn['interface_mode_a']) or ''
        vlan_local = (conn['vlan_id_a'] if local_side else conn['vlan_id_b']) or ''
        vlan_remote = (conn['vlan_id_b'] if local_side else conn['vlan_id_a']) or ''
        # 描述/备注按端独立读取：本端值 + 对端值
        desc = (conn['description_a'] if local_side else conn['description_b']) or ''
        note = (conn['note_a'] if local_side else conn['note_b']) or ''
        desc_remote = (conn['description_b'] if local_side else conn['description_a']) or ''
        note_remote = (conn['note_b'] if local_side else conn['note_a']) or ''
    else:
        cur_dev = cur_port = agg_local = ''
        agg_mode_local = agg_mode_remote = if_mode_local = if_mode_remote = ''
        vlan_local = vlan_remote = ''
        desc = note = desc_remote = note_remote = ''
        other_id = None

    # ---- 左右分栏：本端信息 | 对端信息 ----
    vlans = pu.list_project_vlans(project['id'])
    vlan_opts = [v['value'] for v in vlans]
    if not vlans:
        st.caption('项目暂无 VLAN，请先到项目详情「VLAN 设置」添加')

    left_col, right_col = st.columns(2)

    # ---- 左侧：本端信息 ----
    with left_col:
        st.markdown('**本端信息**')
        # 固定默认值，禁用不可编辑（样式与右侧输入框一致）
        st.text_input('本端设备', value=dev_name_map[dev_id], disabled=True)
        st.text_input('本端端口', value=disp, disabled=True)
        status_in = dict_field('接口状态', 'interface_status',
                               port['interface_status'] or '', 'dlg_status')
        # 接口模式 -> VLAN -> 聚合模式 -> 聚合组（按端独立，联动默认值）
        if_mode_local_in = dict_field('接口模式', 'interface_mode', if_mode_local, 'dlg_if_mode_local')
        vlan_local_in = vlan_multiselect('VLAN', vlan_local, 'dlg_vlan_local', if_mode_local_in, vlans, vlan_opts)
        agg_mode_local_in = dict_field('聚合模式', 'aggregation_mode', agg_mode_local, 'dlg_agg_mode_local')
        agg_local_in = st.text_input('聚合组（本端）', key='dlg_agg_local',
                                     value=agg_local or ('/' if agg_mode_local_in == '/' else ''),
                                     placeholder='如 11' if agg_mode_local_in != '/' else '不聚合')
        # 连接描述（本端）/ 备注（本端）：按端独立存储
        desc_left_in = st.text_input('连接描述（本端，留空自动生成）', value=desc, key='dlg_desc_left')
        note_left_in = st.text_input('备注（本端）', value=note, key='dlg_note_left', placeholder='选填')

    # ---- 右侧：对端信息 ----
    with right_col:
        st.markdown('**对端信息**')
        # 对端设备（含"无连接"）
        dev_opts = ['（无连接）'] + [d['name'] for d in devices if d['id'] != dev_id]
        cur_idx = dev_opts.index(cur_dev) if cur_dev in dev_opts else 0
        dev_sel = st.selectbox('对端设备', dev_opts, index=cur_idx)

        # 对端接口（随对端设备联动，仅标准模板端口）
        if dev_sel != '（无连接）':
            tdev = next(d for d in devices if d['name'] == dev_sel)
            # 未占用端口 + 当前已连接的端口（编辑既有连接时可重新选中自己）
            tports = [p for p in pu.get_device_ports(tdev['id'])
                      if not p['is_used'] or (conn and other_id == p['id'])]
            opts = [pu.port_display_name(p) for p in tports]
            if cur_port and cur_port not in opts:
                opts.append(cur_port)  # 存量连接的对端端口仍可显示
            cur_idx2 = opts.index(cur_port) if cur_port in opts else 0
            port_sel = st.selectbox('对端接口 :red[*]', opts, index=cur_idx2)

        # 对端参数（与对端信息对称，编辑即写对端端口/对端各字段；无连接时不显示）
        if dev_sel != '（无连接）':
            cur_rstatus = ''
            if conn:
                cur_rstatus = (conn['port_b_status'] if local_side else conn['port_a_status']) or ''
            rstatus_in = dict_field('接口状态（对端）', 'interface_status', cur_rstatus or 'UP', 'dlg_rstatus')
            if_mode_remote_in = dict_field('接口模式（对端）', 'interface_mode', if_mode_remote, 'dlg_if_mode_remote')
            vlan_remote_in = vlan_multiselect('VLAN（对端）', vlan_remote, 'dlg_vlan_remote', if_mode_remote_in, vlans, vlan_opts)
            agg_mode_remote_in = dict_field('聚合模式（对端）', 'aggregation_mode', agg_mode_remote, 'dlg_agg_mode_remote')
            cur_ragg = ''
            if conn:
                cur_ragg = (conn['aggregation_group_b'] if local_side else conn['aggregation_group_a']) or ''
            ragg_in = st.text_input('聚合组（对端）', key='dlg_agg_remote',
                                    value=cur_ragg or ('/' if agg_mode_remote_in == '/' else ''),
                                    placeholder='如 11' if agg_mode_remote_in != '/' else '不聚合')
        else:
            rstatus_in = if_mode_remote_in = vlan_remote_in = agg_mode_remote_in = ragg_in = ''

        # 连接描述（对端）/ 备注（对端）：按端独立存储
        desc_right_in = st.text_input('连接描述（对端，留空自动生成）', value=desc_remote, key='dlg_desc_right')
        note_right_in = st.text_input('备注（对端）', value=note_remote, key='dlg_note_right', placeholder='选填')

    if st.button('💾 保存', type='primary'):
        # 组装单行数据交给同步引擎
        if dev_sel == '（无连接）':
            final_dev = final_port = ''
        else:
            final_dev = dev_sel
            final_port = port_sel
        row = {
            '接口': disp, '接口状态': status_in, '聚合组': agg_local_in,
            '聚合模式': agg_mode_local_in, '聚合模式（对端）': agg_mode_remote_in,
            '接口模式': if_mode_local_in, '接口模式（对端）': if_mode_remote_in,
            'VLAN': vlan_local_in, 'VLAN（对端）': vlan_remote_in,
            '描述': desc_left_in, '备注': note_left_in,
            '对端设备': final_dev, '对端接口': final_port,
            '接口状态（对端）': rstatus_in, '聚合组（对端）': ragg_in,
            '对端描述': desc_right_in, '对端备注': note_right_in,
        }
        result = cu.sync_device_rows(project['id'], dev_id, [row])
        parts = []
        if result['created']:
            parts.append(f'新增 {result["created"]} 条')
        if result['updated']:
            parts.append(f'更新 {result["updated"]} 条')
        if result['deleted']:
            parts.append(f'删除 {result["deleted"]} 条')
        msg = '保存成功：' + ('、'.join(parts) if parts else '无变化')
        if result['vlan_added']:
            msg += f'；VLAN 自动新增 {len(result["vlan_added"])} 个'
        if result['dict_added']:
            msg += f'；字典新增 {len(result["dict_added"])} 项'
        if result['errors']:
            for e in result['errors']:
                st.error(e)
            return  # 有失败留在弹窗中修正
        st.session_state['flash'] = ('success', msg)
        st.rerun()


# ---------------- 批量连线弹窗 ----------------
@st.dialog('⚡ 批量连线', width='large')
def batch_link_dialog(dev_id):
    """批量连线：本端多端口 ↔ 对端多台（固定端口）/ 多端口，参数一套套全部，预检后批量保存"""
    st.caption(f'本端设备：**{dev_name_map[dev_id]}**　按列表顺序一一对应连线')

    # ---- 本端端口（未占用） ----
    local_ports = [p for p in pu.get_device_ports(dev_id) if not p['is_used']]
    local_opts = [pu.port_display_name(p) for p in local_ports]
    if not local_opts:
        st.info('本端设备没有空闲端口，请先释放或删除已有连接')
        return
    sel_local = st.multiselect(f'本端端口（空闲 {len(local_opts)} 个）', local_opts, key='bl_local')

    # ---- 对端方式 ----
    mode = st.radio('对端方式', ['多台设备 × 固定端口', '单台设备 × 多个端口'],
                    horizontal=True, key='bl_mode',
                    help='多台×固定端口：本端口 1 ↔ 对端设备 1（各设备端口同名）；'
                         '单台×多端口：本端口 1 ↔ 对端端口 1（同一台设备）')
    other_devs = [d for d in devices if d['id'] != dev_id]
    if not other_devs:
        st.warning('项目内只有这一台设备，无法批量连线')
        return
    if mode == '多台设备 × 固定端口':
        sel_devs = st.multiselect('对端设备（按列表顺序与本端端口一一对应）',
                                  [d['name'] for d in other_devs], key='bl_devs')
        # 对端固定端口名：下拉选择所选设备共同拥有的端口；无交集时降级手动输入
        if sel_devs:
            common = pu.common_device_ports(project['id'], sel_devs)
            if common:
                fix_port = st.selectbox('对端固定端口名 :red[*]（所选设备共同拥有）',
                                        common, key='bl_fix_port')
            else:
                fix_port = st.text_input('对端固定端口名 :red[*]', placeholder='如 NIC01',
                                         key='bl_fix_port_in')
                st.caption('所选设备没有共同端口，请手动输入，或调整设备选择')
        else:
            fix_port = st.text_input('对端固定端口名 :red[*]', placeholder='如 NIC01',
                                     key='bl_fix_port_in')
        n_remote = len(sel_devs)
    else:
        sel_dev = st.selectbox('对端设备', [d['name'] for d in other_devs], key='bl_dev')
        tdev = next(d for d in other_devs if d['name'] == sel_dev)
        r_ports = [p for p in pu.get_device_ports(tdev['id']) if not p['is_used']]
        r_opts = [pu.port_display_name(p) for p in r_ports]
        sel_rports = st.multiselect('对端端口（空闲，按顺序与本端一一对应）', r_opts, key='bl_rports')
        n_remote = len(sel_rports)
        fix_port = ''

    # ---- 数量校验 ----
    n_local = len(sel_local)
    can_link = False
    if n_local and n_remote:
        if n_local == n_remote:
            st.success(f'数量匹配：{n_local} 个本端端口 ↔ {n_remote} 个对端，可以连线')
            can_link = True
        else:
            st.error(f'数量不匹配：本端 {n_local} 个、对端 {n_remote} 个，需一致才能连线')

    # ---- 参数（左右对称，一套套全部） ----
    st.divider()
    st.markdown('**连接参数（应用到全部连线，留空按默认规则）**')
    vlans = pu.list_project_vlans(project['id'])
    vlan_opts = [v['value'] for v in vlans]
    if not vlans:
        st.caption('项目暂无 VLAN，请先到项目详情「VLAN 设置」添加')
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('**本端参数**')
        (status_in, if_mode_local_in, vlan_local_in, agg_mode_local_in,
         agg_local_in, desc_local_in, note_local_in) = _param_block(
             'bl_l', '', vlans, vlan_opts,
             agg_placeholder='留空或单值=全部相同；空格分隔 N 值=逐口对应')
    with c2:
        st.markdown('**对端参数**')
        (rstatus_in, if_mode_remote_in, vlan_remote_in, agg_mode_remote_in,
         ragg_in, desc_remote_in, note_remote_in) = _param_block(
             'bl_r', '（对端）', vlans, vlan_opts,
             agg_placeholder='留空或单值=全部相同；空格分隔 N 值=逐口对应')

    if st.button('⚡ 批量连线', type='primary', disabled=not can_link):
        # 本端/对端聚合组：单值套全部 / 空格分隔 N 值逐口对应（数量不符报错不保存）
        try:
            agg_values = pu.split_agg_values(agg_local_in, n_local)
            ragg_values = pu.split_agg_values(ragg_in, n_remote)
        except ValueError as e:
            st.error(str(e))
            return
        rows = []
        for i, disp in enumerate(sel_local):
            if mode == '多台设备 × 固定端口':
                rdev, rport = sel_devs[i], fix_port.strip()
            else:
                rdev, rport = sel_dev, sel_rports[i]
            rows.append({
                '接口': disp, '接口状态': status_in, '聚合组': agg_values[i],
                '聚合模式': agg_mode_local_in, '聚合模式（对端）': agg_mode_remote_in,
                '接口模式': if_mode_local_in, '接口模式（对端）': if_mode_remote_in,
                'VLAN': vlan_local_in, 'VLAN（对端）': vlan_remote_in,
                '描述': desc_local_in, '备注': note_local_in,
                '对端设备': rdev, '对端接口': rport,
                '接口状态（对端）': rstatus_in, '聚合组（对端）': ragg_values[i],
                '对端描述': desc_remote_in, '对端备注': note_remote_in,
            })
        # 整批预检：任一条失败则不保存（整批回滚）
        errors = cu.precheck_batch_rows(project['id'], dev_id, rows)
        if errors:
            st.error(f'预检未通过（{len(errors)} 条），本次批量未保存：')
            for e in errors:
                st.write(f'- {e}')
            return
        result = cu.sync_device_rows(project['id'], dev_id, rows)
        msg = f'批量连线完成：新增 {result["created"]} 条'
        if result['errors']:
            msg += f"；有 {len(result['errors'])} 条异常（" + '；'.join(result['errors'][:3]) + '）'
        st.session_state['flash'] = ('success', msg)
        st.rerun()


# ---------------- 侧边栏：设备区（全部设备列表 + 添加） ----------------
def _move_device_order(project_id, dev_id, delta):
    """设备上下移一位：交换相邻 sort_order 并重编号（侧边栏与导出顺序同步）"""
    ordered = [d['id'] for d in pu.get_project_devices(project_id)]
    idx = ordered.index(dev_id)
    j = idx + delta
    if j < 0 or j >= len(ordered):
        return False
    ordered[idx], ordered[j] = ordered[j], ordered[idx]
    pu.reorder_project_devices(project_id, ordered)
    return True


dev_id_sel = st.session_state.get('dev_sel')
if dev_id_sel is not None and dev_id_sel not in [d['id'] for d in devices]:
    dev_id_sel = None  # 选中设备已被删除等情况
with st.sidebar:
    st.markdown('**设备**')
    if not devices:
        st.caption('暂无设备')
    else:
        # 全部设备竖排按钮列表：所有设备一眼可见，选中高亮，设备多时侧边栏自动滚动
        for d in devices:
            total, used = pu.get_device_stats(d['id'])
            if st.button(f"{d['name']}（{used}/{total}）", key=f'dev_btn_{d["id"]}',
                         type='primary' if d['id'] == dev_id_sel else 'secondary',
                         width='stretch'):
                dev_id_sel = d['id']
                st.session_state['dev_sel'] = dev_id_sel
                st.rerun()
        if st.button('➕ 添加设备', width='stretch'):
            add_device_dialog()
        # 设备排序：一组上移/下移，作用于当前选中的设备
        dev_idx = next((i for i, x in enumerate(devices) if x['id'] == dev_id_sel), None)
        can_order = dev_idx is not None and len(devices) > 1
        c1, c2 = st.columns(2)
        with c1:
            if st.button('⬆ 上移', key='dev_up', width='stretch',
                         disabled=not (can_order and dev_idx > 0),
                         help='移动当前选中的设备（侧边栏高亮的那台）'):
                _move_device_order(project['id'], dev_id_sel, -1)
                st.rerun()
        with c2:
            if st.button('⬇ 下移', key='dev_down', width='stretch',
                         disabled=not (can_order and dev_idx < len(devices) - 1),
                         help='移动当前选中的设备（侧边栏高亮的那台）'):
                _move_device_order(project['id'], dev_id_sel, +1)
                st.rerun()

if dev_id_sel is None:
    st.info('暂无设备，请在侧边栏点击「添加设备」创建')
    st.stop()

# ---------------- 只读网格 + 单击行高亮选中 ----------------
df = _build_grid_df(dev_id_sel)
view = df.copy()  # 保留原 index，用于映射回真实行号
if st.session_state.get('show_connected_only'):
    view = view[view['对端设备'] != ''].copy()  # 「已连接」筛选：只显示有链路的端口

# 高度固定显示约 18 行（行高约 35px + 表头 40px），其余行表格内滚动
event = st.dataframe(
    view, key=f'grid_{dev_id_sel}', hide_index=True, width='stretch',
    height=40 + 35 * 18,
    selection_mode='single-row', on_select='rerun',
    column_order=['本端设备', '位置', '接口', '接口状态', '聚合组', '聚合模式', '接口模式',
                  'VLAN', '对端设备', '对端接口', '描述', '备注'],
)

# 读取选中行：优先用返回值事件，session_state 兜底
sel_rows = []
if event is not None:
    sel = getattr(event, 'selection', None)
    if sel is not None:
        sel_rows = list(sel.get('rows', []) or [])
if not sel_rows:
    _state = st.session_state.get(f'grid_{dev_id_sel}')
    if isinstance(_state, dict):
        sel_rows = list(_state.get('selection', {}).get('rows', []) or [])

# 按钮行：等宽列布局（按钮统一大小）
bc1, bc2, bc3, bc4, bc5, bc6, bc7 = st.columns(7)
if bc1.button('✏️ 编辑所选行', type='primary', key='btn_edit_row', width='stretch'):
    if not sel_rows:
        st.warning('请先单击表格中的一行（高亮选中）')
    else:
        sel_row = int(sel_rows[0])
        if sel_row < len(view):
            # view.index 保留原表行号（筛选不影响映射）
            orig_idx = int(view.index[sel_row])
            edit_row_dialog(dev_id_sel, orig_idx)
        else:
            st.warning('选中行无效，请重新选择')
if bc2.button('⚡ 批量连线', key='btn_batch_link', width='stretch',
              help='本端多端口一次连多台设备（固定端口）或多端口（单台设备），配置一套套全部'):
    batch_link_dialog(dev_id_sel)
if bc3.button('✏️ 批量编辑设备', key='btn_batch_edit_dev', width='stretch',
              help='一次查看全部设备，逐台修改名称/位置/管理IP/BMC IP'):
    batch_edit_device_dialog()
if bc4.button('🗑 删除设备', key='btn_del_dev', width='stretch', help='删除当前选中的设备'):
    delete_device_dialog(next(d for d in devices if d['id'] == dev_id_sel))
if bc5.button('📋 设备预览', key='btn_tpl_preview', width='stretch',
              help='显示设备区所有设备及其模板、IP、端口占用'):
    template_preview_dialog()
# 显示已连接端口 / 显示所有端口：按连接状态过滤端口表格
conn_only = st.session_state.get('show_connected_only', False)
if bc6.button('显示已连接端口', type='primary' if conn_only else 'secondary',
              key='btn_conn_only', width='stretch', help='只显示已建立连接的端口'):
    st.session_state['show_connected_only'] = True
    st.rerun()
if bc7.button('显示所有端口', type='primary' if not conn_only else 'secondary',
              key='btn_all_conn', width='stretch', help='显示全部端口'):
    st.session_state['show_connected_only'] = False
    st.rerun()
