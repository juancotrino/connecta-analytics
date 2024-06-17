import os
import importlib
from dotenv import load_dotenv

import importlib
from PIL import Image

import streamlit as st

import firebase_admin

from app.modules.styling import apply_default_style, footer
from app.modules.authenticator import get_authenticator, get_page_roles
from app.modules.utils import get_authorized_pages_names

# # Dictionary to map tab names to functions
# tab_functions = {
#     "Segment SPSS": importlib.import_module('app.pages.01_Segment_SPSS').main,
#     "Transform to Belcorp": importlib.import_module('app.pages.02_Transform_to_Belcorp').main,
#     "NOEL Dashboard": importlib.import_module('app.pages.03_NOEL_Dashboard').main,
#     "New Project Initialization": importlib.import_module('app.pages.04_New_Project_Initialization').main,
#     "Tools": importlib.import_module('app.pages.05_Tools').main,
# }

# modules = {' '.join(file.split('.')[0].split('_')[1:]): file.split('.')[0] for file in sorted(os.listdir('app/pages')) if not file.startswith('_')}

# test = {'Segment SPSS': importlib.import_module('app.pages.Segment_SPSS')}

files = [file.split('.')[0] for file in sorted(os.listdir('app/pages')) if not file.startswith('_')]
# modules = {file.split('.')[0]: importlib.import_module(f"app.pages.{file.split('.')[0]}").main for file in files}

# print(modules)

# # Dictionary to map tab names to functions
# tab_functions = {}

# # Dynamically import modules and populate tab_functions
# for tab_name, module_path in modules.items():
#     module = importlib.import_module(module_path)
#     tab_functions[tab_name] = module.main

load_dotenv()

# -------------- SETTINGS --------------
page_title = "Analytics Interface"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

apply_default_style(
    page_title,
    page_icon,
    page_type='login'
)

authenticator = get_authenticator()

def home():
    print('user roles', st.session_state['roles'])
    pages_roles = get_page_roles()
    pages_names = get_authorized_pages_names(pages_roles)

    print('pages roles:', pages_roles)
    print('pages names:', pages_names)

    _ = authenticator.login_panel
    _ = authenticator.hide_unauthorized_pages(pages_roles)
    if st.session_state.get('roles'):
        if 'connecta-admin' in st.session_state['roles']:
            with st.expander("Administrator options"):
                try:
                    _ = authenticator.register_user_form
                except Exception as e:
                    st.error(e)

    if pages_names:
        st.sidebar.markdown("# Available components")
        tabs = st.tabs(pages_names)
        for page_name, tab in zip(pages_names, tabs):
            with tab:
                i = importlib.import_module(f"app.pages.{page_name.replace(' ', '_')}")
                i.main()
        footer()


def main():
    st.sidebar.markdown("# Home")

    container = st.container()

    st.title(page_title)

    # --- DROP DOWN VALUES FOR SELECTING THE PERIOD ---
    logo = Image.open('static/images/connecta.png')

    container.image(logo, width=500)

    # noinspection PyProtectedMember
    if not firebase_admin._apps:
        app_options = {'projectId': 'connecta-analytics-app'}
        firebase_admin.initialize_app(options=app_options)

    cookie_is_valid = authenticator.cookie_is_valid
    # not_logged_in = authenticator.not_logged_in

    if not cookie_is_valid and authenticator.not_logged_in:
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

    home()

main()
