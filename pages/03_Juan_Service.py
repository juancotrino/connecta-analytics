from PIL import Image
import streamlit as st

from modules.styling import apply_default_style
from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp

# -------------- SETTINGS --------------
page_title = "Juan Stiven Service"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

# --------------------------------------

apply_default_style(
    page_title,
    page_icon,
    initial_sidebar_state='expanded'
)

st.sidebar.markdown("# Transformation to Belcorp")
st.sidebar.markdown("""
This tool helps Juan to create something
""")

st.title(page_title)
st.header('My first argument')
