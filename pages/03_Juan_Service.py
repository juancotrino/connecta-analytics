from PIL import Image
import streamlit as st

from modules.styling import apply_default_style
from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp
from modules.text_function import questionFinder
from modules.text_function import genRecodes
from modules.text_function import genLabels

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
st.header('Tools')

with st.expander("Question Finder"):
    entryText=st.text_area("Text Entry:",placeholder="Copy and paste the entire text of the questionnaire")
    btnFinder=st.button("Find")
    if btnFinder:
        st.text_area("Questions:",questionFinder(entryText))
        st.success("Copy to clipboard")


with st.expander("Generate Recodes"):
    entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars column from the base")
    btnFinder=st.button("Generate Recodes")
    if btnFinder:
        st.text_area("Recodes:",genRecodes(entryText))
        st.success("Copy to clipboard")
        st.download_button(
            label="Download Sintaxis",
            data=genRecodes(entryText),
            file_name=f'Sintaxis1.sps'
        )

with st.expander("Generate Labels"):
    entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars column from the base ")
    entryText2=st.text_area("Options:",placeholder="Copy and paste the Values options column from the base ")
    btnFinder=st.button("Generate Labels")
    if btnFinder:
        st.text_area("Labels:",genLabels(entryText,entryText2))
        st.success("Copy to clipboard")
