# -*- coding: utf-8 -*-
"""页面2：项目管理（项目列表 / 进入 / 删除 / Excel 导入）"""
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


st.set_page_config(page_title='项目管理', page_icon='📂', layout='wide')
apply_layout()
st.title('📂 项目管理')
flash_msg()


# ---------------- 创建项目（弹窗：名称 + 描述） ----------------
@st.dialog('➕ 创建项目')
def create_project_dialog():
    name = st.text_input('项目名称 :red[*]', placeholder='如 数据中心一期')
    desc = st.text_input('项目描述', placeholder='选填')
    if st.button('创建项目', type='primary', width='stretch'):
        if not name.strip():
            st.error('项目名称不能为空')
            return
        project_id, final_name = pu.create_project(name.strip(), desc.strip())
        st.session_state['flash'] = ('success', f'项目「{final_name}」已创建，点击列表中的「进入」开始配置')
        st.rerun()  # 关闭弹窗，留在项目管理页


# ---------------- 删除项目 ----------------
@st.dialog('删除项目')
def delete_project_dialog(project):
    st.warning(f"确定删除项目「{project['name']}」？其全部设备、端口、连接数据将一并删除，且不可恢复。")
    if st.button('确认删除'):
        pu.delete_project(project['id'])
        st.session_state['flash'] = ('success', f"项目「{project['name']}」已删除")
        st.rerun()


# ---------------- 页面主体 ----------------
if st.button('➕ 创建项目', type='primary'):
    create_project_dialog()

projects = pu.list_projects()
if not projects:
    st.info('暂无项目。点击「创建项目」新建。')
    st.stop()

st.caption(f'共 {len(projects)} 个项目')
for p in projects:
    with st.container(border=True):
        cols = st.columns([2.2, 1.4, 1, 1, 1.2, 1.2])
        cols[0].markdown(f"**{p['name']}**")
        cols[1].write(p['created_at'][:19])
        cols[2].write(f"{p['device_count']} 台设备")
        cols[3].write(f"{p['conn_count']} 条连接")
        if cols[4].button('进入', key=f'enter_{p["id"]}', width='stretch'):
            # 同时写入 session_state：刷新页面时也能找到项目
            st.session_state['current_project_id'] = p['id']
            st.query_params['project_id'] = str(p['id'])
            st.switch_page('views/项目详情.py')
        if cols[5].button('删除', key=f'del_{p["id"]}', width='stretch'):
            delete_project_dialog(p)
