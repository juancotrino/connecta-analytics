import pandas as pd

import streamlit as st

from app.modules.processing import processing
from app.modules.preprocessing import preprocessing

def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool calculates significant differences and formats the processing tables from SPSS in an `.xlsx` format.
    """)

    st.header('SPSS Tables')

    st.markdown('### Preprocessing')

    with st.form('preprocessing_form'):

        st.markdown('#### Database')

        st.write("Load `.sav` database file to be formatted.")

        # Add section to upload a file
        uploaded_file_sav = st.file_uploader("Upload `.sav` file", type=["sav"], key='preprocessing_sav')

        config = {
            'visit_name': st.column_config.TextColumn('Visit Name', width='small', required=True),
        }

        st.markdown('#### Visits names')

        visit_names = st.data_editor(
            pd.DataFrame(columns=[k for k in config.keys()]),
            num_rows="dynamic",
            width=400,
            key="visit_names_df",
            column_config=config
        )

        visit_names_list = visit_names['visit_name'].to_list()

        process = st.form_submit_button('Preprocess database')

        if uploaded_file_sav and process:
            with st.spinner('Processing...'):
                try:
                    preprocessing_results = preprocessing(uploaded_file_sav, visit_names_list)
                    st.success('Database preprocessed successfully.')
                except Exception as e:
                    st.error(e)

    try:
        st.download_button(
            label="Download processed database",
            data=preprocessing_results.getvalue(),
            file_name=f'processed_database.sav',
            mime='application/sav',
            type='primary'
        )
    except:
        pass


    st.markdown('### SPSS Processing')

    with st.form('processingSPSS_form'):
        # Add section to upload a file
        uploaded_file_sav_processing_pro = st.file_uploader("Upload `.sav` file", type=["sav"], key='preprocessingSPSS_sav')

        # Add section to upload a file
        uploaded_file_processing_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"], key='processingSPSS_xlsx')

    st.markdown('### Processing')

    with st.form('processing_form'):

        st.write("Load excel file with the processing tables from SPSS.")

        # Add section to upload a file
        uploaded_file_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"], key='processing_xlsx')

        process = st.form_submit_button('Process file')

        if uploaded_file_xlsx and process:
            with st.spinner('Processing...'):
                results = processing(uploaded_file_xlsx)
                st.success('Tables processed successfully.')

    try:
        st.download_button(
            label="Download processed tables",
            data=results.getvalue(),
            file_name=f'processed_tables.xlsx',
            mime='application/xlsx',
            type='primary'
        )
    except:
        pass
