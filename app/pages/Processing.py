import pandas as pd

import streamlit as st

from app.modules.processing import processing
from app.modules.preprocessing import preprocessing
from app.modules.processor import (
    getPreProcessCode,
    getProcessCode,
    getSegmentCode,
    getPenaltysCode,
    getCruces,
    getPreProcessAbiertas
)
from app.modules.penalty import calculate_penalties

def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool calculates significant significance and penalties and formats the processing tables from SPSS in an `.xlsx` format.
    """)

    st.header('SPSS Tables')

    st.markdown('### Processing')

    with st.form('processingSPSS_form'):
        uploaded_file_process_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"], key='processingSPSS_xlsx')
        uploaded_file_process_sav = st.file_uploader("Upload `.sav` file", type=["sav"], key='preprocessingSPSS_sav')
        processButton = st.form_submit_button('Get code to process')
        if processButton and uploaded_file_process_xlsx and uploaded_file_process_sav:
            col1, col2   = st.columns(2)

            with col1:
                col1.markdown("Preprocess code:")
                with col1.container(height=250):
                    st.code(getPreProcessCode(uploaded_file_process_sav,uploaded_file_process_xlsx), line_numbers=True)
            with col2:
                col2.markdown("Code to segment base by references:")
                with col2.container(height=250):
                    st.code(getSegmentCode(uploaded_file_process_sav), line_numbers=True)
            st.markdown("### Code SPSS")
            col1, col2, col3  = st.columns(3)
            with col1:
                col1.markdown("Code to gen Tables in SPSS:")
                with col1.container(height=250):
                    st.code(getProcessCode(uploaded_file_process_sav,uploaded_file_process_xlsx), line_numbers=True)

            with col2:
                col2.markdown("Code to gen Penaltys Tables in SPSS:")
                with col2.container(height=250):
                    st.code(getPenaltysCode(uploaded_file_process_xlsx), line_numbers=True)

            with col3:
                col3.markdown("Code to gen Cruces Tables in SPSS:")
                with col3.container(height=250):
                    st.code(getCruces(uploaded_file_process_xlsx), line_numbers=True)

            st.markdown("#### Code Abiertas")
            col1, col2 = st.columns(2)
            with col1:
                col1.markdown("Code to preprocess Abiertas in SPSS:")
                with col1.container(height=250):
                    st.code(getPreProcessAbiertas(uploaded_file_process_sav,uploaded_file_process_xlsx), line_numbers=True)

            with col2:
                col2.markdown("Code to gen Abiertas tables in SPSS:")
                with col2.container(height=250):
                    st.code("none", line_numbers=True)

    st.markdown('### Transform Database')

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

    st.markdown('### Statistical Significance | Penalties')

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
