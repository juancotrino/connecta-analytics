import streamlit as st

from app.modules.new_proejct_initialization import create_folder_structure
from app.modules.utils import get_countries

def main():
    # -------------- SETTINGS --------------

    try:
        countries_iso_2_code = get_countries()
    except Exception as e:
        countries_iso_2_code = {'Colombia': 'CO'}
        st.error(e)

    st.markdown("""
    This is a tool that allows the creation of a folder tree structure for a new project
    in a SharePoint directory that will be used by the Data Science team.
    """)
    st.header('Project Basic Information')

    with st.form('noel_project'):

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

        create_button = st.form_submit_button('Create folder structure')

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
