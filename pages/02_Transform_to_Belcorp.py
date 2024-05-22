import requests

import pandas as pd
from PIL import Image
import streamlit as st

from modules.styling import apply_default_style, apply_404_style
# from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp

# -------------- SETTINGS --------------
page_title = "Transformation to Belcorp"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

# --------------------------------------

role = st.session_state.get("role")
auth_status = st.session_state.get("authentication_status")

if role not in ('connecta-ds',) or auth_status is not True:
    apply_404_style()

else:

    apply_default_style(
        page_title,
        page_icon,
        initial_sidebar_state='expanded'
    )

    st.sidebar.markdown("# Transformation to Belcorp")
    st.sidebar.markdown("""
    This tool helps to convert Connecta's databases (SPSS) into the defualt format used by client Belcorp.

    Write the study name and upload an excel file with required sheets `MAPEO` and `ESPECIFICACIONES`.
    Upload the `.sav` database of the study to be processed.
    """)

    st.title(page_title)
    st.header('Study information')

    col, buff = st.columns([1, 3])

    study = col.text_input('Study name:', help='This is the name that the output file will have.')

    st.write("Load excel file with variable mapping and project specifications and `.sav` database.")

    # Add section to upload a file
    uploaded_file_xlsx = st.file_uploader("Upload Excel file", type=["xlsx"])
    uploaded_file_sav = st.file_uploader("Upload SAV file", type=["sav"])


    if study and uploaded_file_xlsx and uploaded_file_sav:

        results = transform_to_belcorp(study, uploaded_file_xlsx, uploaded_file_sav)

        # Offer the sav file for download
        st.download_button(
            label="Generate Transformation",
            data=results.getvalue(),
            file_name=f'BBDD NORMAS - {study}.sav',
            mime='application/sav'
        )
