import json
from dotenv import load_dotenv

from PIL import Image

import streamlit as st

import firebase_admin

from modules.styling import apply_default_style, footer
from modules.authenticator import get_authenticator, get_page_roles

load_dotenv()

# -------------- SETTINGS --------------
page_title = "Analytics Interface"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

apply_default_style(
    page_title,
    page_icon,
)

authenticator = get_authenticator()

def home():
    _ = authenticator.login_panel
    pages_roles = get_page_roles()
    _ = authenticator.hide_unauthorized_pages(pages_roles)
    if st.session_state.get('roles'):
        if 'connecta-admin' in st.session_state['roles']:
            with st.expander("User registration"):
                try:
                    _ = authenticator.register_user_form
                except Exception as e:
                    st.error(e)

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

    cookie_is_valid = authenticator.cookie_is_valid
    print('cookie_is_valid', cookie_is_valid)
    # not_logged_in = authenticator.not_logged_in

    print(st.session_state["authentication_status"])
    print(st.session_state)

    if not cookie_is_valid and authenticator.not_logged_in:
        print('ENTRAAAAAAAAAAAAAAAAAAAAAAAAAA**********************')
        st.markdown("""
            <style>
                [data-testid="collapsedControl"] {
                    display: none
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        footer()
        return None

    st.write(
        """
    Please expand the menu with the arrow on the top left hand corner
    to see the available services.
        """
    )
    # st.write(st.session_state)
    home()

    footer()

main()
