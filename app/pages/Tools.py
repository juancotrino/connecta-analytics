import streamlit as st
import pandas as pd

from app.modules.text_function import questionFinder, genLabels
from app.modules.coder import transform_open_ended, generate_open_ended_db
from app.modules.processing import get_totals_from_pretables
from app.modules.processor import get_comparison_tables, get_lc_comparison
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
            with st.container(height=200):
                st.code(questionFinder(entryText))

    with st.expander("Generate Labels"):
        entryText=st.text_area("Questions:",placeholder="Copy and paste the list of questions",height=200)
        entryText2=st.text_area("Labels SPSS:",placeholder="Copy and paste the label column from SPSS")
        btnFinder=st.button("Generate Labels")
        if btnFinder:
            with st.container(height=300):
                st.code(genLabels(entryText,entryText2))

    with st.expander("Get totals from Pretablas:"):
        pretabla_xlsx=st.file_uploader("Upload `.xlsx` file", type=["xlsx"], key='pretabla_xlsx')
        btn_get_totals=st.button("Get Totals")
        if btn_get_totals:
            with st.spinner('Get totals...'):
                results_totals = get_totals_from_pretables(pretabla_xlsx)
                st.success('Tables totals generate successfully.')
        try:
            try_download('Download totals tables', results_totals, 'totals_tables', 'xlsx')
        except:
            pass

    with st.expander("Compare 2 Bases SAV Files:"):
        col1, col2 = st.columns(2)
        with col1:
            comparebases1_sav=st.file_uploader("Upload `.sav` file", type=["sav"], key='comparebases1_sav')
        with col2:
            comparebases2_sav=st.file_uploader("Upload `.sav` file", type=["sav"], key='comparebases2_sav')
        btn_get_comparison=st.button("Get Comparison")
        if btn_get_comparison:
            with st.spinner('Get Comparison...'):
                results_totals2 = get_comparison_tables(comparebases1_sav,comparebases2_sav)
                st.success('Comparison generate successfully.')
        try:
            try_download('Download Comparison tables', results_totals2, 'comparison_tables', 'xlsx')
        except:
            pass


    # with st.expander("Generate List of Includes"):
    #     entryText=st.text_area("Variables:",placeholder="Copy and paste the Vars from the GeneraAxis")
    #     entryText2=st.text_area("Nums:",placeholder="Copy and paste the num column from the includes Excel")
    #     entryText3=st.text_area("Table:",placeholder="Copy and paste the table from the includes Excel")
    #     entryText4=st.text_area("Table Depured:",placeholder="Copy and paste the table depured from the includes Excel")
    #     entryText5=st.text_area("Nums2:",placeholder="Copy and paste the num column oftable depured from the includes Excel")
    #     btnFinder=st.button("Generate Includes List")
    #     if btnFinder:
    #         st.text_area("Labels:",genIncludesList(entryText,entryText2,entryText3,entryText4,entryText5))

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

    with st.expander("Compare LC Files:"):
        col1, col2 = st.columns(2)
        with col1:
            comparelc1_xlsx=st.file_uploader("Upload `.xlsx` file", type=["xlsx", "xlsm"], key='comparelc1_xlsx')
        with col2:
            comparelc2_xlsx=st.file_uploader("Upload `.xlsx` file", type=["xlsx", "xlsm"], key='comparelc2_xlsx')
        btn_get_comparison=st.button("Get LC Comparison")
        if btn_get_comparison:
            with st.spinner('Get LC Comparison...'):
                results_comparelc = get_lc_comparison(comparelc1_xlsx,comparelc2_xlsx)
                st.success('LC Comparison generate successfully.')
        try:
            try_download('Download LC Comparison tables', results_comparelc, 'lccomparison_tables-'+comparelc1_xlsx.name[:10]+'-'+comparelc2_xlsx.name[:10], 'xlsx')
        except:
            pass

    with st.expander("SPSS split and join"):
        st.markdown('### Split')
        with st.form('split_spss_form'):
            split_file = st.file_uploader("Upload `.sav` file", type=["sav"], key="split_file_sav")
            number_of_records = st.number_input('Number of records per chunk', step=1, min_value=1)

            split_database = st.form_submit_button('Split database')

            if split_file and number_of_records and split_database:
                original_file_name = split_file.name.split('.')[0]
                temp_split_file = get_temp_file(split_file)
                chunks, meta = split_sav_file_to_chunks(temp_split_file, number_of_records)
                zip_buffer = create_zip_with_chunks(chunks, meta, original_file_name)
            elif not split_file and split_database:
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
            elif not (original_db and join_files) and join_databases:
                st.error('Upload all required files.')

        try:
            try_download('Download joined database', joined_database, 'db_joined', 'sav')
        except:
            pass
