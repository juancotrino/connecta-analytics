from PIL import Image
import streamlit as st

from modules.styling import apply_default_style, apply_404_style
from modules.new_proejct_initialization import create_directory_structure

# -------------- SETTINGS --------------
page_title = "New Project Initialization"
page_icon = Image.open('static/images/connecta-logo.png')  # emojis: https://www.webfx.com/tools/emoji-cheat-sheet/

authorized_roles = (
    'connecta-ds',
)
# --------------------------------------

roles = st.session_state.get("roles")
auth_status = st.session_state.get("authentication_status")

if not roles or any(role not in authorized_roles for role in roles) or auth_status is not True:
    apply_404_style()

else:

    apply_default_style(
        page_title,
        page_icon,
        initial_sidebar_state='expanded'
    )

    st.sidebar.markdown("# New Project Initialization")
    st.sidebar.markdown("""
    This is a tool that allows the creation of a folder tree structure for a new project
    in a SharePoint directory that will be used by the Data Science team.
    """)

    st.title(page_title)
    st.header('Project Basic Information')

    col11, col12 = st.columns(2)

    project_id = col11.text_input('Project ID')
    project_id = project_id.strip()
    if project_id:
        try:
            project_id = int(project_id)
        except:
            project_id = None
            st.warning('Project ID should be a number.')

    project_name = col12.text_input('Project name')
    project_name = project_name.strip().lower().replace(' ', '_')

    id_project_name = f'{project_id}_{project_name}'

    if st.button('Create folder structure') and project_id and project_name:
        create_directory_structure(id_project_name)
        st.markdown('Folder created with the structure:')
        import subprocess
        result = subprocess.run(['tree', id_project_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        st.code(result.stdout)
