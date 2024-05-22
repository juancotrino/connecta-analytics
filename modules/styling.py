from PIL.Image import Image

import streamlit as st

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
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """

    st.markdown(
        hide_st_style,
        unsafe_allow_html=True
    )

    # Execute local_css function only once at the start of the app
    local_css("static/style.css")


def apply_404_style():
    # --- HIDE STREAMLIT STYLE ---
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

    local_html('static/404.html')
