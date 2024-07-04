import ast

import pandas as pd

import streamlit as st

from app.modules.new_proejct_initialization import (
    get_temp_file,
    read_sav_metadata,
    create_folder_structure,
    get_projects_info
)
from app.modules.utils import get_countries

def main():
    # -------------- SETTINGS --------------

    try:
        countries_iso_2_code = get_countries()
    except Exception as e:
        countries_iso_2_code = {'Colombia': 'CO'}
        st.error(e)

    try:
        projects_info = get_projects_info()
        categories = tuple(projects_info['categories'])
        sub_categories = tuple(projects_info['sub_categories'])
        clients = tuple(projects_info['clients'])
        variables = tuple(projects_info['variables'])
    except Exception as e:
        st.error(e)

    st.markdown("""
    This is a tool that allows the creation of a folder tree structure for a new project
    in a SharePoint directory that will be used by the Data Science team.
    """)

    st.header('Database')

    uploaded_file_sav = st.file_uploader("Upload `.sav` file", type=["sav"], key='noel_transform_sav')

    if uploaded_file_sav:
        temp_file_name = get_temp_file(uploaded_file_sav)
        metadata_df = read_sav_metadata(temp_file_name)
        metadata_df['answer_options_count'] = metadata_df['values'].apply(lambda x: len(ast.literal_eval(x)) if x else 0).astype(int)
        st.markdown('### File metadata')
        st.dataframe(
            metadata_df,
            use_container_width=True
        )

    st.header('Project Information')

    with st.form('noel_project'):



        col1, col2, col3 = st.columns(3)

        with col1:
            project_id = st.text_input('Project ID').strip()
            if project_id:
                try:
                    _ = int(project_id)
                except:
                    project_id = None
                    st.warning('Project ID should be a number.')

            categories = st.selectbox(
                'Categories',
                options=categories,
                index=None,
                placeholder="Select category..."
            )

        with col2:
            country = st.selectbox(
                'Country',
                options=countries_iso_2_code.keys(),
                index=None,
                placeholder="Select country..."
            )

            categories = st.selectbox(
                'Subcategories',
                options=sub_categories,
                index=None,
                placeholder="Select subcategory..."
            )

        with col3:
            project_name = st.text_input('Project name')
            project_name = project_name.strip().lower().replace(' ', '_')

            clients = st.selectbox(
                'Subcategories',
                options=clients,
                index=None,
                placeholder="Select client..."
            )

        config = {
            'variable_name': st.column_config.TextColumn('Variable Name', width='large', disabled=True),
            'variable_in_db': st.column_config.TextColumn('Variable in DB', width='small')
        }

        variables_mapping = st.data_editor(
            pd.DataFrame({'variable_name': variables}, columns=[k for k in config.keys()]),
            num_rows="dynamic",
            use_container_width=True,
            key="variables_mapping_df",
            column_config=config
        )

        if country:
            country_code = countries_iso_2_code[country].lower()

            id_project_name = f'{project_id}_{country_code}_{project_name}'

        create_button = st.form_submit_button('Process database')

        if project_id and country and project_name:
            if create_button:
                base_path = f'Documentos compartidos/estudios_externos/{id_project_name}'
                try:
                    with st.spinner('Processing...'):
                        create_folder_structure(base_path)
                        # folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios_externos/{id_project_name}'
                        # st.success(
                        #     f'Study root folder created successfully. Visit the new folder [here]({folder_url}).'
                        # )
                except Exception as e:
                    st.error(e)
