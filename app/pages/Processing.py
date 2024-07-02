import streamlit as st

from app.modules.processing import processing

def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool calculates significant differences and formats the processing tables from SPSS in an `.xlsx` format.
    """)

    st.header('SPSS Tables')

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
