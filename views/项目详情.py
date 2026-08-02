# -*- coding: utf-8 -*-
"""项目详情（设备平铺选择 + 筛选 + 单击行高亮 + 编辑弹窗）

不显示在侧边栏，只能从「项目管理 → 进入」打开。
交互流程：顶部选择设备卡片 -> 筛选（仅显示UP/显示All）-> 单击行高亮选中
-> 「✏️ 编辑所选行」弹窗中填写对端设备/端口/参数 -> 保存即生效。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    st.warning('请选择要查看的项目：')
    names = [p['name'] for p in projects]
    sel = st.selectbox('选择项目', names, key='pick_project')
    if st.button('进入项目', type='primary'):
        chosen = next(p for p in projects if p['name'] == sel)
        st.session_state['current_project_id'] = chosen['id']
        st.query_params['project_id'] = str(chosen['id'])
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
top = st.columns([1, 1.2, 1.2, 1.2, 1.2])
if top[0].button('← 返回项目列表', width='stretch'):
    st.switch_page('views/项目管理.py')


@st.dialog('添加设备')
def add_device_dialog():
    from utils import template_utils as tu
    templates = tu.list_templates()
    if not templates:
        st.warning('模板库为空，请先到「模板管理」页面创建模板')
        return
    t_label = {t['id']: f"{t['model']}（{tu.type_label(t['type'])}，{t['port_count']} 口）" for t in templates}
    tpl_id = st.selectbox('设备模板', list(t_label.keys()), format_func=lambda x: t_label[x])
    name = st.text_input('设备名称 :red[*]')
    location = st.text_input('位置/机架', placeholder='选填，如 H10')
    if st.button('添加设备'):
        if not name.strip():
            st.error('设备名称不能为空')
            return
        try:
            pu.add_project_device(project['id'], tpl_id, name.strip(), location.strip())
            st.session_state['flash'] = ('success', f'设备「{name.strip()}」已添加，端口已克隆')
            st.rerun()
        except ValueError as e:
            st.error(str(e))


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


@st.dialog('📶 VLAN 设置（本项目）')
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


@st.dialog('📋 设备模板预览')
def template_preview_dialog():
    st.caption(f'共 {len(devices)} 台设备')
    st.dataframe(
        [{'设备': d['name'], '模板': d['model'] or '自由设备（无模板）',
          '位置': d['location'] or '-',
          '端口占用': f"{pu.get_device_stats(d['id'])[1]}/{pu.get_device_stats(d['id'])[0]}"}
         for d in devices],
        hide_index=True, width='stretch')


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
if top[3].button('📶 VLAN 设置', width='stretch'):
    vlan_dialog()
if top[4].button('🔄 刷新', width='stretch'):
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
                '聚合模式': conn['aggregation_mode'] or '',
                '接口模式': conn['interface_mode'] or '',
                'VLAN': conn['vlan_id'] or '',
                '对端设备': conn['device_b_name'] if local_side else conn['device_a_name'],
                '对端接口': cu.conn_port_b_display(conn) if local_side else cu.conn_port_a_display(conn),
                '描述': conn['description'] or '',
                '备注': conn['note'] or '',
            })
        else:
            rows.append({'本端设备': dev_name, '位置': dev_location, '接口': disp,
                         '接口状态': p['interface_status'] or '',
                         '聚合组': '', '聚合模式': '', '接口模式': '', 'VLAN': '',
                         '对端设备': '', '对端接口': '', '描述': '', '备注': ''})
    return pd.DataFrame(rows)


# ---------------- 编辑行弹窗 ----------------
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
        agg_mode = conn['aggregation_mode'] or ''
        if_mode = conn['interface_mode'] or ''
        vlan = conn['vlan_id'] or ''
        desc = conn['description'] or ''
        note = conn['note'] or ''
    else:
        cur_dev = cur_port = agg_local = agg_mode = if_mode = vlan = desc = note = ''
        other_id = None

    # ---- 左右分栏：本端信息 | 对端信息 ----
    def dict_field(label, category, current, key):
        """全局字典下拉（标准值，不提供自定义输入；存量字典外的值仍可显示）"""
        values = [v['value'] for v in pu.list_dict(category)]
        if current and current not in values:
            values.append(current)
        idx = values.index(current) if current in values else 0
        return st.selectbox(label, values, index=idx, key=key)

    left_col, right_col = st.columns(2)

    # ---- 左侧：本端信息 ----
    with left_col:
        st.markdown('**本端信息**')
        # 固定默认值，禁用不可编辑（样式与右侧输入框一致）
        st.text_input('本端设备', value=dev_name_map[dev_id], disabled=True)
        st.text_input('本端端口', value=disp, disabled=True)
        status_in = dict_field('接口状态', 'interface_status',
                               port['interface_status'] or '', 'dlg_status')
        agg_local_in = st.text_input('聚合组（本端）', value=agg_local, placeholder='如 Agg-1')
        # 连接描述：左右两侧对齐（同一连接字段，保存时以改动过的一侧为准）
        desc_left_in = st.text_input('连接描述（留空自动生成）', value=desc, key='dlg_desc_left')

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

        # 对端接口状态 / 聚合组：与对端信息对称，编辑即写对端端口/对端聚合组
        if dev_sel != '（无连接）':
            cur_rstatus = ''
            if conn:
                cur_rstatus = (conn['port_b_status'] if local_side else conn['port_a_status']) or ''
            rstatus_in = dict_field('接口状态（对端）', 'interface_status', cur_rstatus or 'UP', 'dlg_rstatus')
            cur_ragg = ''
            if conn:
                cur_ragg = (conn['aggregation_group_b'] if local_side else conn['aggregation_group_a']) or ''
            ragg_in = st.text_input('聚合组（对端）', value=cur_ragg, placeholder='如 Agg-1')
        else:
            rstatus_in = ragg_in = ''

        desc_right_in = st.text_input('连接描述（留空自动生成）', value=desc, key='dlg_desc_right')
        note_in = note  # 备注已不在界面维护，保存时保留原值

    # ---- 公共参数（左右放置，横线分隔） ----
    st.divider()
    st.markdown('**公共参数**')
    c1, c2 = st.columns(2)
    with c1:
        agg_mode_in = dict_field('聚合模式', 'aggregation_mode', agg_mode, 'dlg_agg_mode')
    with c2:
        if_mode_in = dict_field('接口模式', 'interface_mode', if_mode, 'dlg_if_mode')
    # VLAN：从项目 VLAN 字典多选，空格分隔存储
    vlans = pu.list_project_vlans(project['id'])
    vlan_opts = [v['value'] for v in vlans]
    cur_vlans = [x for x in vlan.split() if x]
    for v in cur_vlans:
        if v not in vlan_opts:
            vlan_opts.append(v)  # 旧数据中字典外的值也允许保留选中
    vlan_sel = st.multiselect(
        'VLAN（多选）', vlan_opts, default=cur_vlans,
        format_func=lambda v: (f"{v}（{next((x['name'] for x in vlans if x['value'] == v), '')}）"
                               if any(x['value'] == v and x['name'] for x in vlans) else v),
        help='多选，保存时以空格分隔（如 160 161）')
    if not vlans:
        st.caption('项目暂无 VLAN，请先到项目详情「VLAN 设置」添加')
    vlan_in = ' '.join(vlan_sel)

    if st.button('💾 保存', type='primary'):
        # 组装单行数据交给同步引擎
        if dev_sel == '（无连接）':
            final_dev = final_port = ''
        else:
            final_dev = dev_sel
            final_port = port_sel
        row = {
            '接口': disp, '接口状态': status_in, '聚合组': agg_local_in,
            '聚合模式': agg_mode_in, '接口模式': if_mode_in, 'VLAN': vlan_in,
            '描述': desc_left_in, '备注': note_in,
            '对端设备': final_dev, '对端接口': final_port,
            '接口状态（对端）': rstatus_in, '聚合组（对端）': ragg_in,
            '对端描述': desc_right_in,
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


# ---------------- 侧边栏：设备区（全部设备列表 + 添加） ----------------
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

if dev_id_sel is None:
    st.info('暂无设备，请在侧边栏点击「添加设备」创建')
    st.stop()

# ---------------- 只读网格 + 单击行高亮选中 ----------------
df = _build_grid_df(dev_id_sel)
if st.session_state.get('show_up_only'):
    view = df[df['接口状态'] == 'UP'].copy()  # 「仅显示UP端口」快捷筛选
else:
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

# 按钮行：水平容器，按钮并排靠左、内容宽度
with st.container(horizontal=True, horizontal_alignment='left'):
    if st.button('✏️ 编辑所选行', type='primary', key='btn_edit_row'):
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
    # 「仅显示UP端口 / 显示All端口」快捷筛选切换
    up_only = st.session_state.get('show_up_only', False)
    if st.button('仅显示UP端口', type='primary' if up_only else 'secondary',
                 key='btn_up_only', help='表格只显示接口状态为 UP 的行'):
        st.session_state['show_up_only'] = True
        st.rerun()
    if st.button('显示All端口', type='primary' if not up_only else 'secondary',
                 key='btn_show_all', help='显示该设备全部端口'):
        st.session_state['show_up_only'] = False
        st.rerun()
    if st.button('🗑 删除设备', key='btn_del_dev', help='删除当前选中的设备'):
        delete_device_dialog(next(d for d in devices if d['id'] == dev_id_sel))
    if st.button('📋 设备模板预览', key='btn_tpl_preview', help='显示设备区所有设备及其调用的模板'):
        template_preview_dialog()
    # 已连接 / 所有：按连接状态过滤端口表格
    conn_only = st.session_state.get('show_connected_only', False)
    if st.button('已连接', type='primary' if conn_only else 'secondary',
                 key='btn_conn_only', help='只显示已建立连接的端口'):
        st.session_state['show_connected_only'] = True
        st.rerun()
    if st.button('所有', type='primary' if not conn_only else 'secondary',
                 key='btn_all_conn', help='显示全部端口'):
        st.session_state['show_connected_only'] = False
        st.rerun()
