from PIL import Image
import streamlit as st

from modules.styling import apply_default_style
from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp
from modules.text_function import questionFinder

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
textinput1=st.empty()
textinput1.text_area("Complete Text:",height=10)
btn1 =st.button("Process",help="Press this button")
text2=st.text_input("Inputttttt:")
text3=st.text_area("Test text:", height=20)
num=0
if(btn1):
    st.write(text3.title())
    textinput1.text_area("Cambioooo",value=text2.title())
st.text("Hola")

with st.expander("Question Finder"):
    entryText=st.text_area("Text Entry:")
    btnFinder=st.button("Find")
    if btnFinder:
        st.text_area("Questions:",questionFinder(entryText))
