# -*- coding: utf-8 -*-
"""页面5：全局选项字典（接口状态 / 聚合模式 / 接口模式 可扩充）

注：VLAN 是项目级字典，在「项目详情 → VLAN 设置」中维护；
导入或录入遇到字典外的新值会自动加入字典，此处可人工增删整理。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from utils import project_utils as pu
from utils.ui_utils import apply_layout


def flash_msg():
    msg = st.session_state.pop('flash', None)
    if msg:
        kind, text = msg
        (st.success if kind == 'success' else st.error if kind == 'error' else st.info)(text)


st.set_page_config(page_title='选项字典', page_icon='⚙️', layout='wide')
apply_layout()
st.title('⚙️ 选项字典')
st.caption('下拉选项不硬编码，全部来自这里的字典；可任意增删扩充。删除字典值不影响已保存的数据，只是不再出现在下拉中。')
flash_msg()

CATEGORIES = [
    ('interface_status', '接口状态'),
    ('aggregation_mode', '聚合模式'),
    ('interface_mode', '接口模式'),
]

for cat, label in CATEGORIES:
    st.subheader(label)
    values = pu.list_dict(cat)
    st.caption(f'当前 {len(values)} 项')
    if values:
        st.write('　'.join(v['value'] for v in values))
    c1, c2 = st.columns([2, 1], vertical_alignment='bottom')
    new_val = c1.text_input(f'新增{label}', key=f'add_{cat}', placeholder='输入新选项值')
    if c2.button('添加', key=f'btn_{cat}', width='stretch'):
        if not new_val.strip():
            st.error('值不能为空')
        elif pu.add_dict_value(cat, new_val.strip()):
            st.session_state['flash'] = ('success', f'{label}已新增「{new_val.strip()}」')
            st.rerun()
        else:
            st.warning(f'「{new_val.strip()}」已存在')
    if values:
        c3, c4 = st.columns([2, 1], vertical_alignment='bottom')
        del_val = c3.selectbox(f'删除{label}中的选项', [v['value'] for v in values],
                               key=f'del_{cat}')
        if c4.button('删除', key=f'delbtn_{cat}', width='stretch'):
            pu.delete_dict_value(cat, del_val)
            st.session_state['flash'] = ('success', f'已删除「{del_val}」')
            st.rerun()
    st.divider()
