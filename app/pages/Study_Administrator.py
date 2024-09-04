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
    upload_file_to_sharepoint,
    get_last_file_version_in_sharepoint,
    get_upload_files_info,
    get_last_id_number,
    get_number_of_studies,
    create_msteams_card
)
from app.modules.utils import get_countries

def main():
    # -------------- SETTINGS --------------

    st.markdown("""
        This is a study administration tool that displays study information. It also allows
        for the creation, editing, and uploading of files to the study's folder in SharePoint.
    """)

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

    sudies_ids_country = get_sudies_ids_country()
    sudies_ids = sudies_ids_country['study_id'].sort_values().unique().tolist()

    last_id_number = get_last_id_number()

    if last_id_number != max(sudies_ids):
        get_sudies_ids_country.clear()
        st.rerun()

    if 'connecta-field' not in st.session_state['roles']:
        business_data = get_business_data()
        tab1, tab2, tab3, tab4 = st.tabs(['Studies viewer', 'Create study', 'Edit study', 'File uploader'])
    else:
        tab4, = st.tabs(['File uploader'])

    if 'connecta-field' not in st.session_state['roles']:

        with tab1:
            col1, col2, col3, col4, col5 = st.columns(5)
            status = col1.multiselect(
                'Filter by status',
                options=sorted(business_data['statuses']),
                placeholder='Select a status...'
            )

            methodology = col2.multiselect(
                'Filter by methodology',
                options=sorted(business_data['methodologies']),
                placeholder='Select a methodology...'
            )

            study_type = col3.multiselect(
                'Filter by study type',
                options=sorted(business_data['study_types']),
                placeholder='Select a study type...'
            )

            country = col4.multiselect(
                'Filter by country',
                options=sorted(countries_iso_2_code.keys()),
                placeholder='Select a country...'
            )

            client = col5.multiselect(
                'Filter by client',
                options=sorted(business_data['clients']),
                placeholder='Select a cient...'
            )

            number_of_studies = get_number_of_studies(
                status=status,
                methodology=methodology,
                study_type=study_type,
                country=country,
                client=client
            )

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

            paginated_data = get_studies(
                batch_size, batch_size * (current_page - 1),
                status=status,
                methodology=methodology,
                study_type=study_type,
                country=country,
                client=client
            )
            paginated_data = paginated_data.drop(columns='source')
            paginated_data = paginated_data.rename(columns={'supervisor': 'consultant'})

            pagination.dataframe(
                data=paginated_data,
                column_config={column: column.replace('_', ' ').capitalize() for column in paginated_data.columns},
                use_container_width=True
            )

        with tab2:
            st.header('Study Basic Information')

            with st.form('create_study'):

                study_name = st.text_input('Study name').strip()

                methodologies = business_data['methodologies']
                methodologies = st.multiselect(
                    'Methodology',
                    options=methodologies,
                    placeholder="Select methodology..."
                )

                study_types = business_data['study_types']
                study_types = st.multiselect(
                    'Study type',
                    options=study_types,
                    placeholder="Select study type..."
                )

                value = st.number_input(
                    'Study value/price',
                    value=0,
                    # format="",
                    step=1
                )

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
                    'Consultant',
                    options=supervisors,
                    index=None,
                    placeholder="Select consultant..."
                )

                create_button = st.form_submit_button('Create study', type='primary')

                if create_button:
                    with st.spinner('Creating study...'):
                        combinations = list(itertools.product(methodologies, study_types, countries))
                        study_data = {
                            'study_id': [last_id_number + 1] * len(combinations),
                            'study_name': [study_name] * len(combinations),
                            'methodology': [combination[0] for combination in combinations],
                            'study_type': [combination[1] for combination in combinations],
                            'description': [description] * len(combinations),
                            'country': [combination[2] for combination in combinations],
                            'client': [client] * len(combinations),
                            'value': [value] * len(combinations),
                            'currency': [currency] * len(combinations),
                            'supervisor': [supervisor] * len(combinations),
                            'status': ['Propuesta'] * len(combinations),
                            'source': ['app'] * len(combinations)
                        }
                        create_study_df(study_data)
                    st.success('Study created successfully')


        with tab3:

            study_id = st.selectbox('Study ID', options=reversed(sudies_ids), index=None, placeholder='Select study ID', key='study_id_edit')

            if study_id:

                with st.form('edit_study'):
                    with st.spinner('Fetching study data...'):
                        study_data = get_study_data(study_id)

                    study_name = st.text_input(
                        'Study name',
                        value=study_data['study_name'].values[0],
                        disabled=True if study_data['source'].values[0] == 'app' else False
                    )

                    statuses: list = business_data['statuses']
                    status = st.selectbox(
                        'Status',
                        options=statuses,
                        index=statuses.index(study_data['status'].values[0]),
                        placeholder="Select status..."
                    )

                    methodologies = business_data['methodologies']
                    methodologies = st.multiselect(
                        'Methodology',
                        options=methodologies,
                        default=study_data['methodology'].unique(),
                        placeholder="Select methodology..."
                    )

                    study_types: list = business_data['study_types']
                    study_types_selected = st.multiselect(
                        'Study type',
                        options=study_types + [None],
                        default=study_data['study_type'].unique(),
                        placeholder="Select study type..."
                    )

                    value = st.number_input(
                        'Study value/price',
                        value=int(study_data['value'].values[0]),
                        step=1
                    )

                    currencies = business_data['currencies']
                    currency = st.selectbox(
                        'Currency',
                        options=currencies,
                        index=currencies.index(study_data['currency'].values[0])
                    )

                    clients = business_data['clients']
                    client = st.selectbox(
                        'Client',
                        options=clients,
                        index=clients.index(study_data['client'].values[0]),
                        disabled=True
                    )

                    countries = st.multiselect(
                        'Country',
                        default=study_data['country'].unique(),
                        options=countries_iso_2_code.keys(),
                        placeholder="Select country..."
                    )

                    description = st.text_area(
                        'Description',
                        value=study_data['description'].values[0]
                    )

                    supervisors: list = business_data['supervisors']
                    supervisor = st.selectbox(
                        'Consultant',
                        options=supervisors,
                        index=supervisors.index(study_data['supervisor'].values[0]) if study_data['supervisor'].values[0] in supervisors else 0,
                        placeholder="Select consultant..."
                    )

                    creation_date = study_data['creation_date'].values[0]

                    edit_study = st.form_submit_button('Edit study', type='primary')

                    if edit_study:
                        with st.spinner('Updating study...'):
                            combinations = list(itertools.product(methodologies, study_types_selected, countries))
                            updated_study_data = {
                                'study_id': [study_id] * len(combinations),
                                'study_name': [study_name] * len(combinations),
                                'methodology': [combination[0] for combination in combinations],
                                'study_type': [combination[1] for combination in combinations],
                                'description': [description] * len(combinations),
                                'country': [combination[2] for combination in combinations],
                                'client': [client] * len(combinations),
                                'value': [value] * len(combinations),
                                'currency': [currency] * len(combinations),
                                'creation_date': [creation_date] * len(combinations),
                                'supervisor': [supervisor] * len(combinations),
                                'status': [status] * len(combinations),
                                'source': ['app'] * len(combinations)
                            }
                            update_study_data(updated_study_data)
                        st.success('Study updated successfully')

                        if status == 'En ejecución' and study_data['status'].values[0] != 'En ejecución':
                            countries_folders = {}
                            for country in countries:
                                country_code = countries_iso_2_code[country].lower()
                                id_study_name = f"{study_id}_{country_code}_{study_name.replace(' ', '_').lower()}"
                                base_path = f'Documentos compartidos/estudios/{id_study_name}'
                                try:
                                    with st.spinner('Creating folder in SharePoint...'):
                                        create_folder_structure(base_path)
                                        folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_study_name}'
                                        countries_folders[country] = folder_url
                                        st.success(
                                            f'Study root folder created successfully for country `{country}`. Visit the new folder [here]({folder_url}).'
                                        )
                                except Exception as e:
                                    st.error(e)

                            try:
                                create_msteams_card(
                                    {
                                        'study_id': study_id,
                                        'study_name': study_name,
                                        'methodology': ', '.join(list(set([combination[0] for combination in combinations]))),
                                        'study_type': ', '.join(list(set([combination[1] for combination in combinations]))),
                                        'description': description,
                                        'country': ', '.join(list(set([combination[2] for combination in combinations]))),
                                        'client': client,
                                        'value': f'{"{:,}".format(value).replace(",",".")} {currency}',
                                        'consultant': supervisor,
                                        'status': status,
                                        'study_folder': countries_folders
                                    }
                                )
                            except Exception as e:
                                st.error(e)

    with tab4:

        study_id = st.selectbox('Study ID', options=reversed(sudies_ids), index=None, placeholder='Select study ID', key='study_id_file_uploader')
        if study_id:
            study_data = get_study_data(study_id)
            studies_countries = study_data[study_data['study_id'] == study_id]['country'].sort_values().unique()
            # studies_countries = sudies_ids_country[sudies_ids_country['study_id'] == study_id]['country'].sort_values().unique()

            if len(studies_countries) > 1:
                country = st.selectbox('Country', options=studies_countries, index=None, placeholder='Select study country', key='country_file_uploader')
            elif len(studies_countries) == 1:
                country = st.text_input('Country', studies_countries[0], disabled=True, key='country_file_uploader')
            else:
                country = None

            specific_studies = sudies_ids_country[
                (sudies_ids_country['study_id'] == study_id) &
                (sudies_ids_country['country'] == country)
            ]['study_name'].sort_values().reset_index(drop=True)

            if study_id and country:
                if len(list(set(specific_studies))) > 1:
                    specific_study = st.radio('Select study:', options=specific_studies, index=None)
                else:
                    specific_study = specific_studies[0]

            if study_id and country and specific_study:
                country_code = countries_iso_2_code[country]
                id_study_name = f"{study_id}_{country_code.lower()}_{specific_study.replace(' ', '_').lower()}"
                base_path = f'Documentos compartidos/estudios/{id_study_name}'
                folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_study_name}'

                st.info(f'Upload to `{specific_study}` study for country: {country}')

                files_info = get_upload_files_info()
                if 'connecta-field' in st.session_state['roles']:
                    files_info = {k: v for k, v in files_info.items() if k == 'questionnaire'}

                title = st.selectbox('File to upload', options=sorted([file.replace('_', ' ').capitalize() for file in files_info.keys()]))
                file_info = files_info[title.replace(' ', '_').lower()]
                # for title, file_info in files_info.items():
                #     st.subheader(title.replace('_', ' ').capitalize())

                with st.form(f'upload_{title}_form'):

                    if file_info['acronym'] and file_info['file_type']:
                        uploaded_file = st.file_uploader(
                            f"Upload `.{'` or `.'.join(file_info['file_type'].split(','))}` {title.replace('_', ' ')} file",
                            type=file_info['file_type'].split(','),
                            key=f"{title.replace('_', ' ')}_{file_info['file_type']}"
                        )
                        upload_file = st.form_submit_button(f"Upload {title.replace('_', ' ')}")
                    else:
                        uploaded_file = st.file_uploader(
                            f"Upload {title.replace('_', ' ')} file",
                            type=None,
                            key=f"{title.replace('_', ' ')}"
                        )
                        upload_file = st.form_submit_button(f"Upload {title.replace('_', ' ')}")

                if uploaded_file and upload_file:
                    file_path = file_info['path']
                    file_type = uploaded_file.name.split('.')[-1]
                    if file_info['acronym'] and file_info['file_type']:
                        files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', file_path)
                        files = [file for file in files if file_info['acronym'] in file]
                        if not files:
                            file_name = f"{id_study_name}_{file_info['acronym']}_V1.{file_type}"
                        else:
                            last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                            file_name = f"{id_study_name}_{file_info['acronym']}_V{last_version_number + 1}.{file_type}"
                    else:
                        file_name = uploaded_file.name

                    with st.spinner(f"Uploading {title.replace('_', ' ')} to Sharepoint..."):
                        try:
                            upload_file_to_sharepoint(f'{base_path}/{file_path}', uploaded_file, file_name)
                            st.success(
                                f"{title.replace('_', ' ').capitalize()} uploaded successfully into [study's folder]({folder_url}/{file_path})."
                            )
                        except Exception as e:
                            st.error('There is no folder for this study in SharePoint.')
