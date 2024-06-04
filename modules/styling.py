from PIL.Image import Image

import streamlit as st
from htbuilder import HtmlElement, div, hr, p, styles
from htbuilder.units import percent, px

def apply_default_style(
    page_title: str,
    page_icon: Image | None = None,
    initial_sidebar_state='collapsed',
    page_type: str = 'service',
    layout: str = 'wide'
):

    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state
    )

    if page_type == 'login':
        st.markdown("""
            <style>
                [data-testid="collapsedControl"] {
                    display: none
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def local_css(file_name):
        with open(file_name) as f:
            st.markdown(
                f"<style>{f.read()}</style>",
                unsafe_allow_html=True
            )

    # --- HIDE STREAMLIT STYLE ---
    hide_st_style = """
        <style>
        footer {visibility: hidden;}
        div[data-testid="stDecoration"] {
            visibility: hidden;
            height: 0%;
            position: fixed;
        }
        div[data-testid="stStatusWidget"] {
            visibility: hidden;
            height: 0%;
            position: fixed;
        }
        </style>
    """

    st.markdown(
        hide_st_style,
        unsafe_allow_html=True
    )

    # Execute local_css function only once at the start of the app
    local_css("static/style.css")


def apply_403_style():
    # --- HIDE STREAMLIT STYLE ---
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    hide_st_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """

    st.markdown(
        hide_st_style,
        unsafe_allow_html=True
    )

    def local_html(file_name):
        with open(file_name) as f:
            st.markdown(
                f"<style>{f.read()}</style>",
                unsafe_allow_html=True
            )

    local_html('static/403.html')


def footer_layout(*args):

    style = """
    <style>
      # MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
    </style>
    """

    style_div = styles(
        left=0,
        bottom=0,
        margin=px(0, 0, 0, 0),
        width=percent(100),
        text_align="center",
        height="60px",
        opacity=0.6
    )

    style_hr = styles(
    )

    body = p()
    foot = div(style=style_div)(hr(style=style_hr), body)

    st.markdown(style, unsafe_allow_html=True)

    for arg in args:
        if isinstance(arg, str):
            body(arg)
        elif isinstance(arg, HtmlElement):
            body(arg)

    st.markdown(str(foot), unsafe_allow_html=True)


def footer():
    myargs = [
        "© Copyright 2024 Connecta SAS. All Rights Reserved",
    ]
    footer_layout(*myargs)
