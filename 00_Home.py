import os
import json
from dotenv import load_dotenv

from PIL import Image

import streamlit as st

import firebase_admin

from modules.styling import apply_default_style, footer
from modules.authenticator import Authenticator

load_dotenv()

# -------------- SETTINGS --------------
page_title = "Analytics Interface"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

apply_default_style(
    page_title,
    page_icon,
)

if 'sidebar_state' not in st.session_state:
    st.session_state.sidebar_state = 'collapsed'

authenticator = Authenticator(
    os.getenv('FIREBASE_API_KEY'),
    os.getenv('COOKIE_KEY')
)

def home():
    _ = authenticator.login_panel

def main():
    st.sidebar.markdown("# Home")

    container = st.container()

    st.title(page_title)

    # --- DROP DOWN VALUES FOR SELECTING THE PERIOD ---
    logo = Image.open('static/images/connecta.png')

    container.image(logo, width=500)

    # noinspection PyProtectedMember
    if not firebase_admin._apps:
        cred_json = json.load(open('firebase_key.json'))
        cred = firebase_admin.credentials.Certificate(cred_json)
        firebase_admin.initialize_app(cred)

    if not authenticator.cookie_is_valid and authenticator.not_logged_in:
        st.markdown("""
            <style>
                [data-testid="collapsedControl"] {
                    display: none
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        return None

    st.write(
        """
    Please expand the menu with the arrow on the top left hand corner
    to see the available services.
        """
    )

    home()

    footer()

main()
