import time
from PIL import Image
import streamlit as st
import pandas as pd
import pyreadstat

from app.modules.text_function import categoryFinder, questionFinder
from app.modules.text_function import genRecodes
from app.modules.text_function import genLabels
from app.modules.text_function import genIncludesList
from app.modules.text_function import processSavMulti
from app.modules.text_function import getAbiertasCode
from app.modules.processor import processSav
from app.modules.processor import getVarsSav
from app.modules.processor import getCodeProcess
from app.modules.processor import getCodePreProcess
from app.modules.utils import get_temp_file, write_multiple_df_bytes

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
        entryText=st.text_area("Questions:",placeholder="Copy and paste the list of questions")
        entryText2=st.text_area("Labels SPSS:",placeholder="Copy and paste the label column from SPSS")
        btnFinder=st.button("Generate Labels")
        if btnFinder:
            st.text_area("Labels:",genLabels(entryText,entryText2))


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
            st.text_area("Questions:",getAbiertasCode(entryText))


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
            datasetName=st.text_input("DatasetName (Optional):")
            preproces=st.button("PreProcess")
            if preproces:
                st.text_area("Commands Agrupation:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[0])
                st.text_area("Inverse Recodes:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[1])
                st.text_area("Columns clones:",getCodePreProcess(uploaded_file2,inversVars,colVarsName)[2])
                st.text_area("Filtered Data:",getCodePreProcess(uploaded_file2,inversVars,colVarsName,datasetName)[3])

    with st.expander("Processor test"):
        uploaded_file = st.file_uploader("Upload SAV file", type=["sav"],key="Processor")
        if uploaded_file:
            colVars=st.multiselect("Column Variables:",getVarsSav(uploaded_file))
            qtypes=st.text_area("Questions Types:")
            vars=st.text_area("Variables to process:")
            proces=st.button("Process All")
            if proces and qtypes and vars:
                st.text_area("Commands Tables:",getCodeProcess(uploaded_file,colVars,vars,qtypes))

    with st.expander("Open-ended questions transformation"):
        open_ended_questions_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"], key='open_ended_questions_xlsx')
        if open_ended_questions_xlsx:
            temp_file_name_xlsx = get_temp_file(open_ended_questions_xlsx)

            df = pd.read_excel(temp_file_name_xlsx)
            df[df.columns[0]] = df[df.columns[0]].astype(str)

            config = {
                'questions': st.column_config.TextColumn('Questions', width='medium', required=True),
            }

            st.markdown('#### Groups of questions')

            st.markdown("""
                Add as many question groups as needed. Separate them with a comma `,`.
            """)

            available_questions = df.columns[1:].astype(str)
            st.markdown(f"Avilable questions: `{'`, `'.join(available_questions)}`.")

            with st.form('open_ended_transformation'):
                questions = st.data_editor(
                    pd.DataFrame(columns=[k for k in config.keys()]),
                    num_rows="dynamic",
                    width=400,
                    key="questions_df",
                    column_config=config
                )

                transform = st.form_submit_button('Transform')

                if not questions.empty and transform:

                    melted_df = df.melt(
                        id_vars=[df.columns[0]],
                        value_vars=df.columns[1:],
                        var_name='question_id',
                        value_name='answer'
                    )

                    melted_df[f'{melted_df.columns[1]}-{melted_df.columns[0]}'] = (
                        melted_df[melted_df.columns[1]] + '-' + melted_df[melted_df.columns[0]]
                    )


                    group_questions_dict = {}
                    for i, group in questions.iterrows():
                        group_questions = [question.strip() for question in group['questions'].split(',')]
                        melted_group_questions = melted_df[melted_df[melted_df.columns[1]].isin(group_questions)]
                        melted_group_questions = melted_group_questions[[f'{melted_df.columns[1]}-{melted_df.columns[0]}', melted_df.columns[2]]]
                        group_questions_dict['-'.join(group_questions)] = melted_group_questions

                    transformed = write_multiple_df_bytes(group_questions_dict)


        try:
            st.download_button(
                label="Download transformation",
                data=transformed.getvalue(),
                file_name=f'open-ended-transformed.xlsx',
                mime='application/xlsx',
                type='primary'
            )
        except:
            pass
