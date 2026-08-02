# -*- coding: utf-8 -*-
"""首页：欢迎落地页（不显示在侧边栏，应用启动默认打开）"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from utils.db_utils import query_one
from utils.ui_utils import apply_layout

st.set_page_config(page_title='LLD 网络连接管理工具', page_icon='🔌', layout='wide')
apply_layout()

st.title('🔌 LLD 网络连接管理工具')
st.caption('网络工程师个人使用的 Port Design 规划工具：录一次连接，两端自动可见，一键导出 LLD 交付文档')

c1, c2, c3 = st.columns(3)
c1.metric('设备模板', query_one('SELECT COUNT(*) AS n FROM device_templates')['n'])
c2.metric('项目', query_one('SELECT COUNT(*) AS n FROM projects')['n'])
c3.metric('连接', query_one('SELECT COUNT(*) AS n FROM project_connections')['n'])

st.markdown('''
### 使用流程

1. **📦 模板管理** — 维护设备型号库（网络设备/服务器/其它设备），导入或手工定义端口
2. **📂 项目管理** — 创建新项目、进入项目详情
3. **项目详情** — 录入连接（两端下拉自动匹配，一条链路两端自动可见）、维护端口状态、连接查询、导出 Excel
4. **⚙️ 选项字典** — 扩充设备角色 / 接口状态 / 聚合模式 / 接口模式选项（VLAN 在项目详情中维护）

左侧边栏进入各功能页面。
''')
