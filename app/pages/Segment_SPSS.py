import time
import ast
from datetime import datetime
import pandas as pd
import streamlit as st

from app.modules.help import help_segment_spss
from app.modules.segment_spss import segment_spss, get_temp_file, read_sav_metadata, create_zip, upload_to_gcs, delete_gcs
from app.modules.validations import validate_segmentation_spss_jobs, validate_segmentation_spss_db


def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool helps to segment Connecta's databases (SPSS) to allow easy
    manipulation and particular analysis of different scenarios like the Chi2.

    Find more help info on how to use the tool in the `Help` collapsable section.
    """)

    col1, col2 = st.columns(2)

    with col2:
        # Add section to upload a file
        st.markdown('### File metadata')
        metadata_container = st.container()
        uploaded_file = st.file_uploader("Upload SAV file", type=["sav"], key=__name__)

        if uploaded_file:
            temp_file_name = get_temp_file(uploaded_file)
            metadata_df = read_sav_metadata(temp_file_name)
            metadata_df['answer_options_count'] = metadata_df['values'].apply(lambda x: len(ast.literal_eval(x)) if x else 0).astype(int)
            metadata_container.dataframe(
                metadata_df,
                use_container_width=True
            )

    if 'gcs_path' not in st.session_state:
        st.session_state['gcs_path'] = None

    with col1:
        with st.form('segment_spss_form'):
            st.markdown('### Scenarios for segmentation')
            st.write("Fill the parameters for the segmentation")

            with st.expander("Help"):
                st.markdown(help_segment_spss)

            config = {
                'scenario_name': st.column_config.TextColumn('Scenario Name', width='small', required=True),
                'variables': st.column_config.TextColumn('Variables', required=False),
                'condition': st.column_config.TextColumn('Condition', required=False),
                'cross_variable': st.column_config.TextColumn('Cross Variable (Chi2)', width='small', required=False),
                'chi2_mode': st.column_config.SelectboxColumn('Mode', options=['T2B', 'TB'], default='T2B'),
                'correlation_variables': st.column_config.TextColumn('Correlation Variables', required=False),
            }

            st.markdown('### Scenarios')

            jobs = st.data_editor(
                pd.DataFrame(columns=[k for k in config.keys()]),
                num_rows="dynamic",
                use_container_width=True,
                key="edit_set_of_strings",
                column_config=config
            )

            jobs_df = pd.DataFrame(jobs)

            jobs_df['variables'] = jobs_df['variables'].apply(lambda x: x.replace(' ', '').replace('\n\n', '\n') if x is not None else x)
            jobs_df['condition'] = jobs_df['condition'].apply(lambda x: x.replace(' ', '').replace('\n\n', '\n') if x is not None else x)
            jobs_df['correlation_variables'] = jobs_df['correlation_variables'].apply(lambda x: x.replace(' ', '').replace('\n\n', '\n') if x is not None else x)

            jobs_validated = validate_segmentation_spss_jobs(jobs_df)

            db_validated = False
            if uploaded_file:
                db_validated = validate_segmentation_spss_db(jobs_df, temp_file_name)

            transform_inverted_scales = st.checkbox('Transform inverted scales')

            process = st.form_submit_button('Process scenarios')

            if jobs_validated and db_validated and not jobs_df.empty:
                if uploaded_file and process:
                    with st.spinner('Processing...'):
                        try:
                            files = segment_spss(jobs_df, uploaded_file, transform_inverted_scales)
                            zip_path = create_zip('segmented_data.zip', files)
                            file_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                            st.session_state['gcs_path'] = upload_to_gcs(zip_path, f'segmented_data_{file_timestamp}.zip')
                        except Exception as e:
                            st.error(e)
            elif not uploaded_file and process:
                st.error('Missing SAV file')

    if st.session_state['gcs_path']:

        # Create a button to download the file and execute the additional action
        if st.button('Download segmented data', type='primary'):
            st.markdown(f"""
                <iframe src="{st.session_state['gcs_path']}" ></iframe>
            """, unsafe_allow_html=True)
            time.sleep(1)
            delete_gcs(st.session_state['gcs_path'].split('/')[-1])

            del st.session_state['gcs_path']

            st.rerun()

        # # Send POST request
        # response = requests.post("your_endpoint_url", json=data)

        # # Check if request was successful
        # if response.status_code == 200:
        #     # Perform action to send scenarios
        #     st.write("Scenarios sent!")

        #     # Offer the zip file for download
        #     st.download_button(
        #         label="Download Segmented Data",
        #         data=response.content,
        #         file_name=f"segmented_data_{uploaded_file.name}.zip",
        #         mime="application/zip"
        #     )

        # else:
        #     st.write("Error occurred while processing the request.")
