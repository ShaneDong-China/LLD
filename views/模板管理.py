# -*- coding: utf-8 -*-
"""页面1：模板管理（模板 / 端口维护 + 模板库导入导出）

「编辑」弹窗内用标签页：基本信息 / 端口，保存后不关闭弹窗
（弹窗继承 fragment 行为，控件交互只重跑弹窗内容并自动刷新数据）。

_port_manage_section 放在模块级（__main__ 守卫外），便于测试导入。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from io import BytesIO

import streamlit as st
from utils import template_utils as tu
from utils import template_exchange as te
from utils.ui_utils import apply_layout


def flash_msg():
    msg = st.session_state.pop('flash', None)
    if msg:
        kind, text = msg
        (st.success if kind == 'success' else st.error if kind == 'error' else st.info)(text)


def _port_manage_section(template_id):
    """编辑弹窗「端口」标签页：列表 + 编辑/删除 + 新增"""
    ports = tu.list_ports(template_id)
    if ports:
        st.dataframe(
            [{'接口': p['port_name']} for p in ports],
            hide_index=True, width='stretch')
        st.divider()
        # 改名：下拉选原端口名，输入框填新端口名
        port_ids = [p['id'] for p in ports]
        sel_id = st.selectbox('原端口名', port_ids,
                              format_func=lambda x: next(p['port_name'] for p in ports if p['id'] == x),
                              key=f'port_sel_{template_id}')
        sel = next(p for p in ports if p['id'] == sel_id)
        pname = st.text_input('新端口名 :red[*]', value=sel['port_name'], key=f'port_name_{template_id}_{sel_id}')
        c1, c2 = st.columns(2)
        if c1.button('💾 保存修改', key=f'port_save_{template_id}_{sel_id}', width='stretch'):
            try:
                if not pname.strip():
                    st.error('端口名不能为空')
                else:
                    tu.update_port(sel_id, pname.strip())
                    st.success(f"端口「{pname.strip()}」已保存")
            except ValueError as e:
                st.error(str(e))
        if c2.button('🗑 删除该端口', key=f'port_del_{template_id}_{sel_id}', width='stretch'):
            try:
                tu.delete_port(sel_id)
                st.success(f"端口「{sel['port_name']}」已删除")
            except ValueError as e:
                st.error(str(e))
    else:
        st.caption('该模板还没有端口')
    st.divider()
    with st.form(f'add_port_{template_id}'):
        pname = st.text_input('新增端口名 :red[*]', placeholder='如 Slot2_Fi_10GE_49 / Cu_MGMT')
        if st.form_submit_button('添加端口'):
            if not pname.strip():
                st.error('端口名不能为空')
            else:
                try:
                    tu.add_port(template_id, pname.strip())
                    st.success(f"端口「{pname.strip()}」已添加")
                except ValueError as e:
                    st.error(str(e))


if __name__ == '__main__':
    st.set_page_config(page_title='模板管理', page_icon='📦', layout='wide')
    apply_layout()
    st.title('📦 模板管理')
    flash_msg()

    # ---------------- 新增模板 ----------------
    @st.dialog('新增设备模板')
    def add_template_dialog():
        model = st.text_input('型号 :red[*]', placeholder='如 S7503X-G')
        vendor = st.text_input('厂商', placeholder='如 H3C')
        type_ = st.selectbox('类型', ['network', 'server', 'other'],
                             format_func=tu.type_label)
        description = st.text_input('描述')
        if st.button('创建模板'):
            if not model.strip():
                st.error('型号不能为空')
                return
            try:
                tu.create_template(model.strip(), vendor.strip(), type_, description.strip())
                st.session_state['flash'] = ('success', f'模板「{model.strip()}」已创建')
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # ---------------- 查看模板 ----------------
    @st.dialog('查看模板', width='large')
    def view_template_dialog(template):
        st.subheader(f"{template['model']}（{tu.type_label(template['type'])}）")
        st.caption(f"厂商: {template['vendor'] or '-'}　描述: {template['description'] or '-'}")
        ports = tu.list_ports(template['id'])
        if not ports:
            st.info('该模板还没有端口，请到「编辑 → 新增端口」添加')
            return
        st.dataframe(
            [{'接口': p['port_name']} for p in ports],
            width='stretch', hide_index=True)

    # ---------------- 编辑模板（基本信息 / 编辑端口 / 新增端口） ----------------
    @st.dialog('编辑模板', width='large')
    def edit_template_dialog(template):
        # 弹窗内控件交互只重跑本弹窗（fragment 行为），每次重跑重读最新数据
        template = tu.get_template(template['id'])
        tab_info, tab_ports = st.tabs(['基本信息', '端口'])

        # ---- 基本信息 ----
        with tab_info:
            st.caption('修改只影响以后新建/导入的设备，已在项目中的设备保持创建时的端口副本。')
            model = st.text_input('型号 :red[*]', value=template['model'], key=f'edit_model_{template["id"]}')
            vendor = st.text_input('厂商', value=template['vendor'] or '', key=f'edit_vendor_{template["id"]}')
            type_ = st.selectbox('类型', ['network', 'server', 'other'],
                                 index=['network', 'server', 'other'].index(template['type'])
                                 if template['type'] in ['network', 'server', 'other'] else 0,
                                 format_func=tu.type_label, key=f'edit_type_{template["id"]}')
            description = st.text_input('描述', value=template['description'] or '', key=f'edit_desc_{template["id"]}')
            if st.button('保存修改', type='primary', width='stretch'):
                if not model.strip():
                    st.error('型号不能为空')
                else:
                    try:
                        tu.update_template(template['id'], model.strip(), vendor.strip(), type_, description.strip())
                        st.success(f"模板「{model.strip()}」已保存")
                    except ValueError as e:
                        st.error(str(e))

        # ---- 端口（编辑/删除 + 新增） ----
        with tab_ports:
            _port_manage_section(template['id'])

    # ---------------- 删除模板 ----------------
    @st.dialog('删除模板')
    def delete_template_dialog(template):
        st.warning(f"确定删除模板「{template['model']}」？其全部板卡与端口将一并删除。")
        if st.button('确认删除'):
            try:
                tu.delete_template(template['id'])
                st.session_state['flash'] = ('success', f"模板「{template['model']}」已删除")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # ---------------- 导入模板 ----------------
    @st.dialog('📥 导入模板')
    def import_templates_dialog():
        st.caption('模板库文件要求：带「模板信息」表（型号 | 类型 | 厂商 | 描述），sheet 名 = 型号且必须在信息表中定义；类型以信息表为准，不做推断。型号已存在时自动跳过。')
        f = st.file_uploader('选择 Excel 文件 :red[*]', type=['xlsx'])
        if f is None:
            return
        data = f.getvalue()
        try:
            models, skipped, undefined = te.preview_templates(BytesIO(data))
        except Exception as e:
            st.error(f'文件解析失败: {e}')
            return
        if not models:
            st.error('未解析到任何模板数据，请确认文件符合模板库格式（sheet 名 = 型号，第一行含「接口」表头）')
            return
        for m in undefined:
            st.warning(f'sheet「{m}」在「模板信息」表中未定义，导入时将跳过（需先在信息表添加对应型号行）')
        port_total = sum(models.values())
        new_models = [m for m in models if not tu.get_template_by_model(m)]
        exist_models = [m for m in models if tu.get_template_by_model(m)]
        st.success(f"解析到 **{len(models)}** 个型号、共 **{port_total}** 个端口")
        if exist_models:
            st.caption(f"已存在将跳过: {', '.join(exist_models)}")
        if skipped:
            st.caption(f"跳过 sheet: {', '.join(str(s) for s in skipped)}")
        if st.button('确认导入', type='primary', width='stretch'):
            result = te.import_templates(BytesIO(data))
            msg = f"导入完成：新增模板 **{len(result['created'])}** 个、端口 **{result['port_count']}** 个"
            if result['skipped']:
                msg += f"；跳过 {len(result['skipped'])} 个（已存在）"
            st.session_state['flash'] = ('success', msg)
            st.rerun()

    # ---------------- 导出模板库 ----------------
    @st.dialog('📤 导出模板库')
    def export_templates_dialog():
        if not tu.list_templates():
            st.caption('模板库为空，本次导出为内置示例（S6805-56HF-G，57 口）：照着它的格式填写你的模板，再「导入模板」即可。')
        else:
            st.caption('导出为模板库格式（sheet 名 = 型号，每行一个端口名，如 Slot2_Fi_10GE_41）：可备份/迁移，也可修改后重新导入。')
        bio = te.export_templates()
        st.download_button(
            '下载模板库 Excel', data=bio.getvalue(),
            file_name=te.export_filename(),
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary', width='stretch',
            on_click=lambda: st.session_state.update(close_tpl_export=True))
        if st.session_state.pop('close_tpl_export', False):  # 回调里不能 rerun，用标记在主体关闭
            st.rerun()

    # ---------------- 页面主体 ----------------
    top = st.columns([1.5, 1.5, 1.5, 3.5])
    if top[0].button('➕ 新增模板', type='primary', width='stretch'):
        add_template_dialog()
    if top[1].button('📥 导入模板', width='stretch'):
        import_templates_dialog()
    if top[2].button('📤 导出模板', width='stretch'):
        st.session_state.pop('close_tpl_export', None)
        export_templates_dialog()

    templates = tu.list_templates()
    if not templates:
        st.info('暂无设备模板，点击上方「新增模板」创建，或「导入模板」从 Excel 迁移')
        st.stop()

    st.caption(f'共 {len(templates)} 个模板')
    for t in templates:
        with st.container(border=True):
            cols = st.columns([2.4, 1.2, 1, 1, 3])
            cols[0].markdown(f"**{t['model']}**")
            cols[1].write(t['vendor'] or '-')
            cols[2].write(tu.type_label(t['type']))
            cols[3].write(f"{t['port_count']} 口")
            # 右侧 3 个内容宽度小按钮（不撑满列，靠右）
            with cols[4]:
                with st.container(horizontal=True, horizontal_alignment='right'):
                    if st.button('查看', key=f'view_{t["id"]}'):
                        view_template_dialog(t)
                    if st.button('编辑', key=f'edit_{t["id"]}'):
                        edit_template_dialog(t)
                    if st.button('删除', key=f'del_{t["id"]}'):
                        delete_template_dialog(t)
