import streamlit as st

from app.modules.file_uploader import (
    get_sharepoint_studies,
    upload_file_to_sharepoint,
    get_last_file_version_in_sharepoint,
    get_upload_files_info
)
from app.modules.utils import get_countries

def main():

    st.markdown("""
    Here you can upload files into their respective study folder.
    """)

    st.header('Study')

    st.markdown('Select study to upload files to its corresponding Sharepoint folder.')

    try:
        countries_codes = get_countries()
    except Exception as e:
        st.error(e)

    reversed_countries_codes = {value: key for key, value in countries_codes.items()}

    studies = get_sharepoint_studies('estudios')

    filtered_studies = list(
        set(
            [
                study
                for study in studies
                if (
                    study.split('_')[0].isdigit() and
                    len(study.split('_')[1]) == 2 and
                    study.split('_')[1].upper() in countries_codes.values()
                )
            ]
        )
    )

    sudies_numbers = sorted(list(set([study.split('_')[0] for study in filtered_studies])))

    col1, col2 = st.columns(2)

    study_number = col1.selectbox('Study number', options=sudies_numbers, index=None, placeholder='Select study number')

    studies_countries_codes = [study.split('_')[1].upper() for study in filtered_studies if study.startswith(str(study_number))]
    studies_countries = set([reversed_countries_codes[country_code] for country_code in studies_countries_codes])

    if len(studies_countries) > 1:
        country = col2.selectbox('Country', options=list(set(studies_countries)), index=None, placeholder='Select study country')
    else:
        country = col2.selectbox('Country', options=studies_countries)

    if study_number and country and len(studies_countries_codes) != studies_countries:
        specific_studies = sorted([' '.join(study.split('_')[2:]).title() for study in filtered_studies if study.startswith(f'{study_number}_{countries_codes[country].lower()}')])
        if len(specific_studies) > 1:
            specific_study = st.radio('Select study:', options=specific_studies, index=None)
        else:
            specific_study = specific_studies[0]

    if study_number and country and specific_study:
        country_code = countries_codes[country]
        id_study_name = f"{study_number}_{country_code.lower()}_{specific_study.replace(' ', '_').lower()}"
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
