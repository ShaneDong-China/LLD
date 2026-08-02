# -*- coding: utf-8 -*-
"""界面布局小工具：压缩 Streamlit 默认留白，让内容区更紧凑

注：顶部导航栏（stHeader）与侧边栏保持 Streamlit 默认行为，不做隐藏。
"""

_LAYOUT_CSS = """
<style>
/* 顶部留白 = 刚好避开悬浮导航栏（stHeader），内容从导航栏下方开始 */
.block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: 3.4rem !important;
    padding-bottom: 1rem !important;
}
/* 压缩各级标题的上下边距 */
h1, h2, h3 {
    margin-top: 0 !important;
    margin-bottom: 0.3rem !important;
}
/* 分隔线（st.divider）上方贴紧、下方留 0.5rem */
hr {
    margin-top: 0.15rem !important;
    margin-bottom: 0.75rem !important;
}
/* 按钮默认 2.3rem 太高，压到 1.8rem（模板/项目列表的行高主要被按钮撑起） */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
    min-height: 1.8rem !important;
}
/* 边框卡片内边距默认 1rem，上下减半（st.container(border=True) 的容器类） */
.st-emotion-cache-1ne20ew {
    padding-top: calc(0.5rem - 1px) !important;
    padding-bottom: calc(0.5rem - 1px) !important;
}
/* 侧边栏设备列表：紧凑排列、行间零间隔（只影响含按钮的区块，导航不受影响） */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(
    [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"]) {
    gap: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    min-height: 1.4rem !important;
    justify-content: flex-start !important;  /* 名称左对齐 */
    text-align: left !important;
}
/* 按钮内部文字容器也强制左对齐、撑满宽度 */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] > div,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] > div {
    text-align: left !important;
    width: 100% !important;
}
/* 悬停无任何动作：不换背景、不加深、无阴影 */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background-color: transparent !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
    background-color: rgb(255, 75, 75) !important;  /* 保持选中态原色 */
    box-shadow: none !important;
}
</style>
"""


def apply_layout():
    """在页面顶部调用，注入紧凑布局样式（会话内全局生效）"""
    import streamlit as st
    st.markdown(_LAYOUT_CSS, unsafe_allow_html=True)
