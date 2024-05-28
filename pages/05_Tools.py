from PIL import Image
import streamlit as st
import pyreadstat

from modules.authenticator import get_authenticator
from modules.styling import apply_default_style, apply_403_style
from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp
from modules.text_function import categoryFinder, questionFinder
from modules.text_function import genRecodes
from modules.text_function import genLabels2
from modules.text_function import genIncludesList
from modules.text_function import processSavMulti
from modules.processor import processSav
from modules.processor import getVarsSav
from modules.processor import getCodeProcess

# -------------- SETTINGS --------------
page_title = "Tools"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

authorized_roles = (
    'connecta-ds',
)

apply_default_style(
    page_title,
    page_icon,
    initial_sidebar_state='expanded'
)

authenticator = get_authenticator()
# --------------------------------------

if authenticator.cookie_is_valid and not authenticator.not_logged_in:

    roles = st.session_state.get("roles")
    auth_status = st.session_state.get("authentication_status")

    if not roles or any(role not in authorized_roles for role in roles) or auth_status is not True:
        apply_403_style()

    else:

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


        # with st.expander("Generate Recodes"):
        #     entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars column from the base")
        #     btnFinder=st.button("Generate Recodes")
        #     if btnFinder:
        #         st.text_area("Recodes:",genRecodes(entryText))
        #         st.success("Copy to clipboard")
        #         st.download_button(
        #             label="Download Sintaxis",
        #             data=genRecodes(entryText),
        #             file_name=f'Sintaxis1.sps'
        #         )

        with st.expander("Generate Labels"):
            entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars column from the base ")
            entryText2=st.text_area("Options:",placeholder="Copy and paste the Values options column from the base ")
            btnFinder=st.button("Generate Labels")
            if btnFinder:
                st.text_area("Labels:",genLabels2(entryText))
                st.success("Copy to clipboard")


        with st.expander("Generate List of Includes"):
            entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars from the GeneraAxis")
            entryText2=st.text_area("Nums:",placeholder="Copy and paste the num column from the includes Excel")
            entryText3=st.text_area("Table:",placeholder="Copy and paste the table from the includes Excel")
            btnFinder=st.button("Generate Includes List")
            if btnFinder:
                st.text_area("Labels:",genIncludesList(entryText,entryText2,entryText3))
                st.success("Copy to clipboard")

        with st.expander("Category Question Finder"):
            entryText=st.text_area("Text Entry:",placeholder="Copy and paste the entire text of the questionnaire ")
            btnFinder=st.button("Find Categories")
            if btnFinder:
                st.text_area("Questions:",categoryFinder(entryText))
                st.success("Copy to clipboard")


        with st.expander("Tool Multiquestion"):
            uploaded_file = st.file_uploader("Upload SAV file", type=["sav"])
            if uploaded_file:
                recodes,labels,variables=processSavMulti(uploaded_file)
                st.text_area("RECODES:",recodes)
                st.download_button(
                    label="Save Sintaxis",
                    data=recodes,
                    file_name='Sintaxis.sps',
                    mime='application/sps'
                )
                st.text_area("Labels:",labels)
                st.download_button(
                    label="Save Etiquetas",
                    data=labels,
                    file_name='Etiquetas.txt'
                )
                st.text_area("Variables:",variables)
                st.success("Vars name column copy to clipboard")

        with st.expander("Processor test"):
            qtypes=st.text_area("Questions Types:")
            uploaded_file = st.file_uploader("Upload SAV file ", type=["sav"])
            if uploaded_file:
                colVars=st.multiselect("Column Variables:",getVarsSav(uploaded_file))
                proces=st.button("Process All")
                if proces:
                    st.text_area("Commands",getCodeProcess(uploaded_file,colVars))
