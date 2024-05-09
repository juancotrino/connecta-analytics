import requests

import pandas as pd
from PIL import Image
import streamlit as st

from modules.styling import apply_default_style
from modules.help import help_segment_spss
from modules.segment_spss import segment_spss
from modules.validations import validate_segmentation_spss_jobs, validate_segmentation_spss_db

# -------------- SETTINGS --------------
page_title = "Segment SPSS"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

# --------------------------------------

apply_default_style(
    page_title,
    page_icon
)

st.sidebar.markdown("# Segment SPSS")

st.title(page_title)
st.header('Scenarios for segmentation')
st.write("Fill the parameters for the segmentation")

with st.expander("Help"):
    st.markdown(help_segment_spss)

config = {
    'scenario_name': st.column_config.TextColumn('Scenario Name', width='small', required=True),
    'variables': st.column_config.TextColumn('Variables', required=False),
    'condition': st.column_config.TextColumn('Condition', required=False),
    'cross_variable': st.column_config.TextColumn('Cross Variable (Chi2)', width='small', required=False),
}

jobs = st.data_editor(
    pd.DataFrame(columns=[k for k in config.keys()]),
    num_rows="dynamic",
    use_container_width=True,
    key="edit_set_of_strings",
    column_config=config
)

jobs_df = pd.DataFrame(jobs)

jobs_validated = validate_segmentation_spss_jobs(jobs_df)

# Add section to upload a file
uploaded_file = st.file_uploader("Upload SAV file", type=["sav"])

db_validated = False
if uploaded_file:
    db_validated = validate_segmentation_spss_db(jobs_df, uploaded_file)

if jobs_validated and db_validated and not jobs_df.empty:
    if uploaded_file:
        results = segment_spss(jobs_df, uploaded_file)

        # Offer the zip file for download
        st.download_button(
            label="Generate Segmented Data",
            data=results.getvalue(),
            file_name='segmented_data.zip',
            mime='application/zip'
        )

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
