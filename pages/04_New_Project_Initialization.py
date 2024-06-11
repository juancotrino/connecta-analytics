import time

from PIL import Image
import streamlit as st

from modules.authenticator import get_authenticator, get_page_roles
from modules.styling import apply_default_style, apply_403_style, footer
from modules.new_proejct_initialization import create_folder_structure
from modules.utils import get_countries

# -------------- SETTINGS --------------
page_title = "New Project Initialization"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

page_name = ''.join(i for i in __file__.split('/')[-1] if not i.isdigit())[1:].split('.')[0]

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

countries_iso_2_code = get_countries()

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

    st.sidebar.markdown("# New Project Initialization")
    st.sidebar.markdown("""
    This is a tool that allows the creation of a folder tree structure for a new project
    in a SharePoint directory that will be used by the Data Science team.
    """)

    st.title(page_title)
    st.header('Project Basic Information')

    col11, col12, col13 = st.columns(3)

    project_id = col11.text_input('Project ID')
    project_id = project_id.strip()
    if project_id:
        try:
            _ = int(project_id)
        except:
            project_id = None
            st.warning('Project ID should be a number.')

    country = col12.selectbox(
        'Country',
        options=countries_iso_2_code.keys(),
        index=None,
        placeholder="Select country..."
    )

    project_name = col13.text_input('Project name')
    project_name = project_name.strip().lower().replace(' ', '_')

    if country:
        country_code = countries_iso_2_code[country].lower()

        id_project_name = f'{project_id}_{country_code}_{project_name}'

    if 'create_new_project_button_disabled' not in st.session_state:
        st.session_state['create_new_project_button_disabled'] = True

    if project_id and country and project_name:
        st.session_state['create_new_project_button_disabled'] = False

    create_button = st.button('Create folder structure', disabled=st.session_state['create_new_project_button_disabled'])

    if project_id and country and project_name:
        if create_button:
            base_path = f'Documentos compartidos/estudios/{id_project_name}'
            try:
                with st.spinner('Creating folder in SharePoint...'):
                    create_folder_structure(base_path)
                    folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_project_name}'
                    st.success(
                        f'Study root folder created successfully. Visit the new folder [here]({folder_url}).'
                    )
            except Exception as e:
                st.error(e)

footer()
