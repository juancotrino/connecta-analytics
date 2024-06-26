import streamlit as st

from app.modules.processing import processing

def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool calculates significant differences and formats the processing tables from SPSS in an `.xlsx` format.
    """)

    st.header('SPSS Tables')

    st.write("Load excel file with the processing tables from SPSS.")

    if 'download_button_disabled' not in st.session_state:
        st.session_state['download_button_disabled'] = True

    # Add section to upload a file
    uploaded_file_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"], key='processing_xlsx')

    if uploaded_file_xlsx:
        with st.spinner('Processing...'):
            results = processing(uploaded_file_xlsx)
            st.session_state['download_button_disabled'] = False
            st.success('Tables processed successfully.')

    try:
        st.download_button(
            label="Download processed tables",
            data=results.getvalue(),
            file_name=f'processed_tables.xlsx',
            mime='application/xlsx',
            disabled=st.session_state['download_button_disabled']
        )
    except:
        pass
