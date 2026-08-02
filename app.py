# -*- coding: utf-8 -*-
"""LLD 网络连接管理工具 - 主入口（导航）

侧边栏只显示三个功能页；「首页」为默认落地页、「项目详情」只能从
「项目管理 → 进入」打开，两者均不在侧边栏显示。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from utils.ui_utils import apply_layout

st.set_page_config(page_title='LLD 网络连接管理工具', page_icon='🔌', layout='wide')
apply_layout()

st.navigation([
    st.Page('views/首页.py', title='首页', icon='🔌', default=True, visibility='hidden'),
    st.Page('views/模板管理.py', title='模板管理', icon='📦'),
    st.Page('views/项目管理.py', title='项目管理', icon='📂'),
    st.Page('views/选项字典.py', title='选项字典', icon='⚙️'),
    st.Page('views/项目详情.py', title='项目详情', icon='📂', visibility='hidden'),
]).run()
