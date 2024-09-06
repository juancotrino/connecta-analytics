import streamlit as st
import pandas as pd

from app.modules.text_function import questionFinder
from app.modules.text_function import genLabels
from app.modules.text_function import genIncludesList
from app.modules.text_function import processSavMulti
from app.modules.text_function import getAbiertasCode
from app.modules.processor import getVarsSav
from app.modules.processor import getCodeProcess
from app.modules.processor import getCodePreProcess
from app.modules.coder import transform_open_ended, generate_open_ended_db
from app.modules.utils import (
    get_temp_file,
    write_multiple_df_bytes,
    write_temp_sav,
    split_sav_file_to_chunks,
    create_zip_with_chunks,
    try_download,
    join_sav
)

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
        st.markdown('### First phase')
        open_ended_questions_xlsx = st.file_uploader("Upload `.xlsx` file", type=["xlsx"], key='open_ended_questions_xlsx')
        if open_ended_questions_xlsx:
            temp_file_name_xlsx = get_temp_file(open_ended_questions_xlsx, '.xlsx')

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
                    group_questions_dict = transform_open_ended(questions, df)
                    transformed = write_multiple_df_bytes(group_questions_dict)

        try:
            st.download_button(
                label="Download transformation",
                data=transformed.getvalue(),
                file_name=f'open_ended_transformed.xlsx',
                mime='application/xlsx',
                type='primary'
            )
        except:
            pass

        st.markdown('### Second phase')
        with st.form('open_ended_coded_transformation'):
            open_ended_questions_coded_xlsx = st.file_uploader("Upload `.xlsx` file", type=["xlsx"], key='open_ended_questions_coded_xlsx')
            closed_questions_db_sav = st.file_uploader("Upload `.sav` file", type=["sav"], key='closed_questions_db_sav')

            transform = st.form_submit_button('Transform')

            if open_ended_questions_coded_xlsx and closed_questions_db_sav and transform:
                temp_file_name_xlsx = get_temp_file(open_ended_questions_coded_xlsx, '.xlsx')
                temp_file_name_sav = get_temp_file(closed_questions_db_sav)

                final_df, metadata = generate_open_ended_db(temp_file_name_xlsx, temp_file_name_sav)

                final_db = write_temp_sav(final_df, metadata)

        try:
            st.download_button(
                label="Download transformation",
                data=final_db.getvalue(),
                file_name=f'open_ended_coded_transformed.sav',
                mime='application/sav',
                type='primary'
            )
        except:
            pass

    with st.expander("SPSS split and join"):
        st.markdown('### Split')
        with st.form('split_spss_form'):
            split_file = st.file_uploader("Upload `.sav` file", type=["sav"], key="split_file_sav")
            number_of_records = st.number_input('Number of records per chunk', step=1, min_value=100)

            split_database = st.form_submit_button('Split database')

            if split_file and number_of_records and split_database:
                original_file_name = split_file.name.split('.')[0]
                temp_split_file = get_temp_file(split_file)
                chunks, meta = split_sav_file_to_chunks(temp_split_file, number_of_records)
                zip_buffer = create_zip_with_chunks(chunks, meta, original_file_name)
            else:
                st.error('Upload all required files.')

        try:
            try_download('Download splitted database', zip_buffer, 'db_splitted', 'zip')
        except:
            pass

        st.markdown('### Join')
        with st.form('join_spss_form'):
            st.markdown('#### Original database')
            original_db = st.file_uploader("Upload `.sav` file", type=["sav"], key="join_original_db_sav")

            st.markdown('#### Chunked databases')
            join_files = st.file_uploader("Upload `.sav` file", type=["sav"], key="join_files_sav", accept_multiple_files=True)

            join_databases = st.form_submit_button('Join databases')

            if original_db and join_files and join_databases:
                temp_original_db_file = get_temp_file(original_db)
                temp_join_files = [get_temp_file(join_file) for join_file in join_files]
                joined_database = join_sav(temp_original_db_file, temp_join_files)
            else:
                st.error('Upload all required files.')

        try:
            try_download('Download joined database', joined_database, 'db_joined', 'sav')
        except:
            pass
