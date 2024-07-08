import ast

import pandas as pd

import streamlit as st

from app.modules.noel_proejct_registration import (
    get_temp_file,
    read_sav_metadata,
    create_folder_structure,
    get_studies_info,
    upload_file_to_sharepoint,
    validate_data,
    process_study
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
        studies_info = get_studies_info()
        categories = tuple(studies_info['categories'])
        sub_categories = tuple(studies_info['sub_categories'])
        brands = tuple(studies_info['brands'])
        clients = tuple(studies_info['clients'])
        variables = tuple(studies_info['variables'])
    except Exception as e:
        st.error(e)

    st.markdown("""
    This is a tool that allows the creation of a folder tree structure for a new study
    in a SharePoint directory that will be used by the Data Science team.
    """)

    st.header('Study files')

    uploaded_file_docx = st.file_uploader("Upload `.docx` questionnaire file", type=["docx"], key='noel_transform_docx')

    if 'show_uploader' not in st.session_state:
        st.session_state['show_uploader'] = True

    st.header('Study Information')

    col01, col02 = st.columns(2)

    with col01:
        holder = st.empty()

        uploaded_file_sav = holder.file_uploader("Upload `.sav` database file", type=["sav"], key='noel_transform_sav')

        if uploaded_file_sav:
            sav_file_name = get_temp_file(uploaded_file_sav)
            metadata_df = read_sav_metadata(sav_file_name)
            metadata_df['answer_options_count'] = metadata_df['values'].apply(lambda x: len(ast.literal_eval(x)) if x else 0).astype(int)
            st.markdown('### File metadata')
            st.dataframe(
                metadata_df,
                use_container_width=True,
                height=750
            )
            holder.empty()

    with col02:
        st.markdown('### Variable mapping')
        with st.form('noel_study'):

            col1, col2, col3 = st.columns(3)

            with col1:
                study_id = st.text_input('Study ID').strip()
                if study_id:
                    try:
                        _ = int(study_id)
                    except:
                        study_id = None
                        st.warning('Study ID should be a number.')

                client = st.selectbox(
                    'Client',
                    options=clients,
                    index=None,
                    placeholder="Select client..."
                )

                brand = st.selectbox(
                    'Brand',
                    options=brands,
                    index=None,
                    placeholder="Select client..."
                )

            with col2:
                country = st.selectbox(
                    'Country',
                    options=countries_iso_2_code.keys(),
                    index=None,
                    placeholder="Select country..."
                )

                category = st.selectbox(
                    'Category',
                    options=categories,
                    index=None,
                    placeholder="Select category..."
                )

                sample_variable = col2.text_input('Sample variable').strip()

            with col3:
                study_name = st.text_input('Project name')
                study_name = study_name.strip().lower().replace(' ', '_')

                sub_category = st.selectbox(
                    'Subcategory',
                    options=sub_categories,
                    index=None,
                    placeholder="Select subcategory..."
                )


                sample_variable_type = col3.selectbox(
                    'Sample variable type',
                    options=['Exact', 'With digits'],
                    help="""
                    - Exact: There is only one variable for the samples and its name is unique.

                    - With digits: There are more than one variable refering to a sample.
                    All of them have the same format but with a different digit at the end.

                        Example: The variables have this structure `PROT1`, `PROT2`... `PROT6`.
                        In this case you should input only the text PROT in the field `Sample variable` on the left.
                    """
                )

            if sample_variable and sample_variable_type:
                match sample_variable_type:
                    case 'Exact':
                        sample_variable = f'^{sample_variable}$'
                    case 'With digits':
                        sample_variable = f'^{sample_variable}\d+$'

            if uploaded_file_sav:
                cleaned_metadata_df = metadata_df.copy()
                cleaned_metadata_df.index = cleaned_metadata_df.index.str.split('.').str[0]
                cleaned_metadata_df = cleaned_metadata_df[~cleaned_metadata_df.index.duplicated(keep='first')]
                cleaned_variables = cleaned_metadata_df.index.tolist()

                config = {
                    'question': st.column_config.TextColumn('Variable Name', width='large', disabled=True),
                    'question_code': st.column_config.SelectboxColumn('Variable in DB', width='small', options=cleaned_variables),
                    'is_inverted': st.column_config.CheckboxColumn('Inverted', width='small')
                }

                variables_mapping = st.data_editor(
                    pd.DataFrame({'question': variables, 'is_inverted': False}, columns=[k for k in config.keys()]),
                    num_rows="dynamic",
                    use_container_width=True,
                    key="variables_mapping_df",
                    column_config=config
                ).dropna(subset='question_code').reset_index(drop=True)

                variables_mapping_dict = pd.Series(
                    variables_mapping['question_code'].values,
                    index=variables_mapping['question']
                ).to_dict()

                study_info = {
                    'study_id': study_id,
                    'country': country,
                    'study_name': study_name,
                    'client': client,
                    'category': category,
                    'sub_category': sub_category,
                    'brand': brand,
                    'sample_variable': sample_variable,
                    'variables_mapping': variables_mapping
                }

                # print(variables_mapping_dict)

                if country:
                    country_code = countries_iso_2_code[country].lower()

                    id_study_name = f'{study_id}_{country_code}_{study_name}'

            create_button = st.form_submit_button('Process database')

            if study_id and country and study_name:
                if create_button:
                    try:
                        validate_data(variables_mapping_dict, metadata_df)

                        base_path = f'Documentos compartidos/estudios_externos/{id_study_name}'
                        if uploaded_file_docx and uploaded_file_sav:
                            try:
                                # with st.spinner('Creating folder structure...'):
                                #     create_folder_structure(base_path)
                                #     folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios_externos/{id_study_name}'
                                #     st.success(
                                #         f'Study root folder created successfully. Visit the new folder [here]({folder_url}).'
                                #     )

                                # with st.spinner('Uploading questionnaire and database to Sharepoint...'):
                                #     upload_file_to_sharepoint(base_path, uploaded_file_docx, 'questionnaire.docx')
                                #     upload_file_to_sharepoint(base_path, uploaded_file_sav, 'db.sav')
                                #     st.success(
                                #         f'Questionnaire and database uploaded successfully into above created folder.'
                                #     )

                                with st.spinner('Processing database...'):
                                    process_study(sav_file_name, study_info)
                                    pass
                                    # upload_file_to_sharepoint(uploaded_file_sav)
                                    # st.success(
                                    #     f'Study root folder created successfully. Visit the new folder [here]({folder_url}).'
                                    # )

                            except Exception as e:
                                st.error(e)

                        else:
                            st.error(
                                'A questionnaire in `.docx` format and database in `.sav` format must be attached into the respective fields.'
                            )

                    except Exception as e:
                        st.error(e)
