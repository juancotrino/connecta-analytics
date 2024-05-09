from PIL.Image import Image

import streamlit as st

def apply_default_style(
    page_title: str,
    page_icon: Image | None = None,
    page_type: str = 'service',
    layout: str = 'wide'
):

    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state='collapsed'
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
