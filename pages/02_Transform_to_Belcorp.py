import time
import requests

import pandas as pd
from PIL import Image
import streamlit as st

from modules.authenticator import get_authenticator, get_page_roles
from modules.styling import apply_default_style, apply_403_style, footer
# from modules.help import help_segment_spss
from modules.transform_to_belcorp import transform_to_belcorp
from settings import AUTHORIZED_PAGES_ROLES

# -------------- SETTINGS --------------
page_title = "Transformation to Belcorp"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

page_name = ''.join(i for i in __file__.split('/')[-1] if not i.isdigit())[1:].split('.')[0]
pages_roles = AUTHORIZED_PAGES_ROLES[page_name]

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

footer()
