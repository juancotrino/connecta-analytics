import itertools

import streamlit as st

from app.modules.study_administrator import (
    create_folder_structure,
    get_studies,
    get_business_data,
    create_study_df,
    get_sudies_ids_country,
    get_study_data,
    update_study_data,
    # get_sharepoint_studies,
    upload_file_to_sharepoint,
    get_last_file_version_in_sharepoint,
    get_upload_files_info,
    get_last_id_number,
    get_number_of_studies
)
from app.modules.utils import get_countries

def main():
    # -------------- SETTINGS --------------

    try:
        countries_iso_2_code = get_countries()
    except Exception as e:
        countries_iso_2_code = {
            'Colombia': 'CO',
            'Mexico': 'MX',
            'Ecuador': 'EC',
            'Peru': 'PE'
        }
        st.error(e)

    st.markdown("""
        This is a study administration tool that displays study information. It also allows
        for the creation, editing, and uploading of files to the study's folder in SharePoint.
    """)

    business_data = get_business_data()

    try:
        countries_codes = get_countries()
    except Exception as e:
        st.error(e)

    # reversed_countries_codes = {value: key for key, value in countries_codes.items()}

    # studies = get_sharepoint_studies('estudios')

    # filtered_studies = list(
    #     set(
    #         [
    #             study
    #             for study in studies
    #             if (
    #                 study.split('_')[0].isdigit() and
    #                 len(study.split('_')[1]) == 2 and
    #                 study.split('_')[1].upper() in countries_codes.values()
    #             )
    #         ]
    #     )
    # )

    last_id_number = get_last_id_number()

    sudies_ids_country = get_sudies_ids_country()
    sudies_ids = sudies_ids_country['study_id'].sort_values().unique().tolist()

    if last_id_number != max(sudies_ids):
        get_sudies_ids_country.clear()
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(['Studies viewer', 'Create study', 'Edit study', 'File uploader'])

    with tab1:

        status = st.container()

        number_of_studies = get_number_of_studies()

        pagination = st.container()

        bottom_menu = st.columns((4, 1, 1))
        with bottom_menu[2]:
            batch_size = st.selectbox("Page Size", options=[25, 50, 100])
        with bottom_menu[1]:
            total_pages = (
                int(number_of_studies / batch_size) if int(number_of_studies / batch_size) > 0 else 1
            )
            current_page = st.number_input(
                "Page", min_value=1, max_value=total_pages, step=1
            )
        with bottom_menu[0]:
            st.markdown(f"Page **{current_page}** of **{total_pages}** ")

        paginated_data = get_studies(batch_size, batch_size * (current_page - 1))

        # If last cached study is not the last one in BQ, clear studies cache and rerun
        if current_page == 1 and paginated_data.index.values[0] != last_id_number:
            get_studies.clear()
            st.rerun()

        selected_status = status.selectbox(
            'Filter by status',
            options=paginated_data['status'].unique().tolist(),
            index=None,
            placeholder='Select a status...'
        )

        pagination.dataframe(
            data=paginated_data[paginated_data['status'] == selected_status] if selected_status else paginated_data,
            column_config={column: column.replace('_', ' ').capitalize() for column in paginated_data.columns},
            use_container_width=True
        )

    with tab2:
        st.header('Study Basic Information')

        with st.form('create_study'):

            study_name = st.text_input('Study name').strip()

            study_types = business_data['study_types']
            study_types = st.multiselect(
                'Study type',
                options=study_types,
                placeholder="Select study type..."
            )

            value = st.number_input('Study value/price', value=None)

            currencies = business_data['currencies']
            currency = st.selectbox(
                'Currency',
                options=currencies,
                index=None,
                placeholder="Select currency..."
            )

            clients = business_data['clients']
            client = st.selectbox(
                'Client',
                options=clients,
                index=None,
                placeholder="Select client..."
            )

            countries = st.multiselect(
                'Country',
                options=countries_iso_2_code.keys(),
                placeholder="Select country..."
            )

            description = st.text_area('Description').strip()

            supervisors = business_data['supervisors']
            supervisor = st.selectbox(
                'Supervisor',
                options=supervisors,
                index=None,
                placeholder="Select supervisor..."
            )

            create_button = st.form_submit_button('Create study', type='primary')

            if create_button:
                with st.spinner('Creating study...'):
                    combinations = list(itertools.product(study_types, countries))
                    study_data = {
                        'study_id': [last_id_number + 1] * len(combinations),
                        'study_name': [study_name] * len(combinations),
                        'study_type': [combination[0] for combination in combinations],
                        'description': [description] * len(combinations),
                        'country': [combination[1] for combination in combinations],
                        'client': [client] * len(combinations),
                        'value': [value] * len(combinations),
                        'currency': [currency] * len(combinations),
                        'supervisor': [supervisor] * len(combinations),
                        'status': ['Propuesta'] * len(combinations),
                    }
                    create_study_df(study_data)
                st.success('Study created successfully')


    with tab3:

        col1, col2 = st.columns(2)

        study_id = col1.selectbox('Study ID', options=reversed(sudies_ids), index=None, placeholder='Select study ID', key='study_id_edit')
        studies_countries = sudies_ids_country[sudies_ids_country['study_id'] == study_id]['country'].sort_values()

        if len(studies_countries) > 1:
            country = col2.selectbox('Country', options=studies_countries, index=None, placeholder='Select study country', key='country_edit')
        else:
            country = col2.selectbox('Country', options=studies_countries, key='country_edit')

        if study_id and country and len(studies_countries) > 1:
            specific_studies = sudies_ids_country[
                (sudies_ids_country['study_id'] == study_id) &
                (sudies_ids_country['country'] == country)
            ]['study_name'].sort_values().reset_index(drop=True)
            if len(specific_studies) > 1:
                specific_study = st.radio('Select study:', options=specific_studies, index=None)
        elif study_id and country:
            specific_studies = sudies_ids_country[
                (sudies_ids_country['study_id'] == study_id) &
                (sudies_ids_country['country'] == country)
            ]['study_name'].sort_values().reset_index(drop=True)
            specific_study = specific_studies[0]

        if study_id and country:

            with st.form('edit_study'):
                with st.spinner('Fetching study data...'):
                    study_data = get_study_data(study_id, country)

                study_name = st.text_input(
                    'Study name',
                    value=study_data['study_name'].values[0].replace('_', ' ').capitalize(),
                    disabled=True
                )

                statuses: list = business_data['statuses']
                status = st.selectbox(
                    'Status',
                    options=statuses,
                    index=statuses.index(study_data['status'].values[0].capitalize()),
                    placeholder="Select status..."
                )

                study_types: list = business_data['study_types']
                study_type = st.selectbox(
                    'Study type',
                    options=study_types,
                    index=study_types.index(study_data['study_type'].values[0].capitalize()),
                    placeholder="Select study type..."
                )

                value = st.number_input(
                    'Study value/price',
                    value=study_data['value'].values[0]
                )

                currencies = business_data['currencies']
                currency = st.selectbox(
                    'Currency',
                    options=currencies,
                    index=currencies.index(study_data['currency'].values[0]),
                    disabled=True
                )

                clients = business_data['clients']
                client = st.selectbox(
                    'Client',
                    options=clients,
                    index=clients.index(study_data['client'].values[0]),
                    disabled=True
                )

                country = st.selectbox(
                    'Country',
                    options=countries_iso_2_code.keys(),
                    index=list(countries_iso_2_code.keys()).index(study_data['country'].values[0].capitalize()),
                    placeholder="Select country...",
                    disabled=True
                )

                description = st.text_area(
                    'Description',
                    value=study_data['description'].values[0]
                )

                supervisors: list = business_data['supervisors']
                supervisor = st.selectbox(
                    'Supervisor',
                    options=supervisors,
                    index=supervisors.index(study_data['supervisor'].values[0]),
                    placeholder="Select supervisor..."
                )

                edit_study = st.form_submit_button('Edit study', type='primary')

                if edit_study:
                    with st.spinner('Updating study...'):
                        updated_study_data = {
                            'study_id': study_id,
                            'country': country,
                            'study_type': study_type,
                            'value': value,
                            'description': description,
                            'supervisor': supervisor,
                            'status': status
                        }
                        update_study_data(updated_study_data)
                    st.success('Study updated successfully')

                    if status == 'En ejecución':
                        country_code = countries_iso_2_code[country].lower()
                        id_study_name = f"{study_id}_{country_code}_{study_name.replace(' ', '_').lower()}"
                        base_path = f'Documentos compartidos/estudios/{id_study_name}'
                        try:
                            with st.spinner('Creating folder in SharePoint...'):
                                create_folder_structure(base_path)
                                folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_study_name}'
                                st.success(
                                    f'Study root folder created successfully. Visit the new folder [here]({folder_url}).'
                                )
                        except Exception as e:
                            st.error(e)

    with tab4:

        col1, col2 = st.columns(2)

        study_id = col1.selectbox('Study ID', options=reversed(sudies_ids), index=None, placeholder='Select study ID', key='study_id_file_uploader')

        # studies_countries_codes = [study.split('_')[1].upper() for study in filtered_studies if study.startswith(str(study_id))]
        studies_countries = sudies_ids_country[sudies_ids_country['study_id'] == study_id]['country'].sort_values(ascending=False)

        if len(studies_countries) > 1:
            country = col2.selectbox('Country', options=studies_countries, index=None, placeholder='Select study country', key='country_file_uploader')
        else:
            country = col2.selectbox('Country', options=studies_countries, key='country_file_uploader')

        if study_id and country and len(studies_countries) > 1:
            specific_studies = sudies_ids_country[
                (sudies_ids_country['study_id'] == study_id) &
                (sudies_ids_country['country'] == country)
            ]['study_name'].sort_values()
            if len(specific_studies) > 1:
                specific_study = st.radio('Select study:', options=specific_studies, index=None)
        elif study_id and country:
            specific_studies = sudies_ids_country[
                (sudies_ids_country['study_id'] == study_id) &
                (sudies_ids_country['country'] == country)
            ]['study_name'].sort_values()
            specific_study = specific_studies[0]

        if study_id and country and specific_study:
            country_code = countries_codes[country]
            id_study_name = f"{study_id}_{country_code.lower()}_{specific_study.replace(' ', '_').lower()}"
            base_path = f'Documentos compartidos/estudios/{id_study_name}'
            folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_study_name}'

            st.info(f'Upload to `{specific_study}` study for country: {country}')

            files_info = get_upload_files_info()

            for title, file_info in files_info.items():
                st.subheader(title.replace('_', ' ').capitalize())

                with st.form(f'upload_{title}_form'):
                    uploaded_file = st.file_uploader(
                        f"Upload `.{file_info['file_type']}` {title.replace('_', ' ')} file",
                        type=[file_info['file_type']],
                        key=f"{title.replace('_', ' ')}_{file_info['file_type']}"
                    )
                    upload_file = st.form_submit_button(f"Upload {title.replace('_', ' ')}")

                if uploaded_file and upload_file:
                    file_path = file_info['path']
                    files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', file_path)
                    files = [file for file in files if file_info['acronym'] in file]
                    if not files:
                        file_name = f"{id_study_name}_{file_info['acronym']}_V1.{file_info['file_type']}"
                    else:
                        last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                        file_name = f"{id_study_name}_{file_info['acronym']}_V{last_version_number + 1}.{file_info['file_type']}"

                    with st.spinner(f"Uploading {title.replace('_', ' ')} to Sharepoint..."):
                        upload_file_to_sharepoint(f'{base_path}/{file_path}', uploaded_file, file_name)
                        st.success(
                            f"{title.replace('_', ' ').capitalize()} uploaded successfully into [study's folder]({folder_url}/{file_path})."
                        )
