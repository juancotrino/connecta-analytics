import time
from PIL import Image
import streamlit as st
import pyreadstat

from app.modules.text_function import categoryFinder, questionFinder
from app.modules.text_function import genRecodes
from app.modules.text_function import genLabels2
from app.modules.text_function import genIncludesList
from app.modules.text_function import processSavMulti
from app.modules.processor import processSav
from app.modules.processor import getVarsSav
from app.modules.processor import getCodeProcess
from app.modules.processor import getCodePreProcess

def main():
    # -------------- SETTINGS --------------
    page_title = "Tools"

    # st.sidebar.markdown("## Tools")
    # st.sidebar.markdown("""
    # Explore some miscellany tools for survey exploration and more.
    # """)

    # st.title(page_title)
    # st.header('Tools')
    st.markdown("""
    Explore some miscellany tools for survey exploration and more.
    """)

    with st.expander("Question Finder"):
        entryText=st.text_area("Text Entry:",placeholder="Copy and paste the entire text of the questionnaire")
        btnFinder=st.button("Find")
        if btnFinder:
            st.text_area("Questions:",questionFinder(entryText))


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


    with st.expander("Generate List of Includes"):
        entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars from the GeneraAxis")
        entryText2=st.text_area("Nums:",placeholder="Copy and paste the num column from the includes Excel")
        entryText3=st.text_area("Table:",placeholder="Copy and paste the table from the includes Excel")
        entryText4=st.text_area("Table Depured:",placeholder="Copy and paste the table depured from the includes Excel")
        entryText5=st.text_area("Nums2:",placeholder="Copy and paste the num column oftable depured from the includes Excel")
        btnFinder=st.button("Generate Includes List")
        if btnFinder:
            st.text_area("Labels:",genIncludesList(entryText,entryText2,entryText3,entryText4,entryText5))

    with st.expander("Category Question Finder"):
        entryText=st.text_area("Text Entry:",placeholder="Copy and paste the entire text of the questionnaire ")
        btnFinder=st.button("Find Categories")
        if btnFinder:
            st.text_area("Questions:",categoryFinder(entryText))


    with st.expander("Tool Multiquestion"):
        uploaded_file = st.file_uploader("Upload SAV file", type=["sav"],key="multiquestion")
        if uploaded_file:
            recodes,labels=processSavMulti(uploaded_file)
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

    with st.expander("Preprocessor test"):
        uploaded_file2 = st.file_uploader("Upload SAV file", type=["sav"],key="Preprocessor")
        if uploaded_file2:
            inversVars=st.multiselect("Inverse Variables:",getVarsSav(uploaded_file2))
            colVarsName=st.multiselect("Columns Variables:",getVarsSav(uploaded_file2))
            preproces=st.button("PreProcess")
            if preproces:
                st.text_area("Commands Agrupation:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[0])
                st.text_area("Inverse Recodes:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[1])
                st.text_area("Columns clones:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[2])

    with st.expander("Processor test"):
        uploaded_file = st.file_uploader("Upload SAV file", type=["sav"],key="Processor")
        if uploaded_file:
            colVars=st.multiselect("Column Variables:",getVarsSav(uploaded_file))
            qtypes=st.text_area("Questions Types:")
            vars=st.text_area("Variables to process:")
            proces=st.button("Process All")
            if proces and qtypes and vars:
                st.text_area("Commands Tables:",getCodeProcess(uploaded_file,colVars,vars,qtypes))
