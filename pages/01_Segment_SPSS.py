import time
import requests

import pandas as pd
from PIL import Image
import streamlit as st

from modules.authenticator import get_authenticator, get_page_roles
from modules.styling import apply_default_style, apply_403_style, footer
from modules.help import help_segment_spss
from modules.segment_spss import segment_spss
from modules.validations import validate_segmentation_spss_jobs, validate_segmentation_spss_db
# from settings import AUTHORIZED_PAGES_ROLES

# -------------- SETTINGS --------------
page_title = "Segment SPSS"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

page_name = ''.join(i for i in __file__.split('/')[-1] if not i.isdigit())[1:].split('.')[0]
# authorized_roles = AUTHORIZED_PAGES_ROLES[page_name]

apply_default_style(
    page_title,
    page_icon,
    initial_sidebar_state='expanded'
)

authenticator = get_authenticator()

# --------------------------------------

if not authenticator.cookie_is_valid and authenticator.not_logged_in:
    st.switch_page("00_Home.py")

roles = st.session_state.get("roles")
auth_status = st.session_state.get("authentication_status")

pages_roles = get_page_roles()
_ = authenticator.hide_unauthorized_pages(pages_roles)
authorized_page_roles = pages_roles[page_name]['roles']

if not roles or not any(role in authorized_page_roles for role in roles) or auth_status is not True:
    apply_403_style()
    _, col2, _ = st.columns(3)
    time_left = col2.progress(100)
    footer()

    for seconds in reversed(range(0, 101, 25)):
        time_left.progress(seconds, f'Redirecing to Home page in {seconds // 25 + 1}...')
        time.sleep(1)

    st.switch_page("00_Home.py")

else:

    st.sidebar.markdown("# Segment SPSS")
    st.sidebar.markdown("""
    This tool helps to segment Connecta's databases (SPSS) to allow easy
    manipulation and particular analysis of different scenarios like the Chi2.

    Find more help info on how to use the tool in the `Help` collapsable section.
    """)

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
        'chi2_mode': st.column_config.SelectboxColumn('Mode', options=['T2B', 'TB'], default='T2B'),
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

footer()
