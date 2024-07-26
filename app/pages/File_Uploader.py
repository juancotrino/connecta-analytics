import streamlit as st

from app.modules.file_uploader import (
    get_sharepoint_studies,
    upload_file_to_sharepoint,
    get_last_file_version_in_sharepoint
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

    study_number = col1.selectbox('Study number', options=sudies_numbers, index=None ,placeholder='Select study number')

    studies_countries_codes = [study.split('_')[1].upper() for study in filtered_studies if study.startswith(str(study_number))]
    studies_countries = [reversed_countries_codes[country_code] for country_code in studies_countries_codes]

    country = col2.selectbox('Country', options=studies_countries, index=None ,placeholder='Select study country')

    if study_number and country:
        country_code = countries_codes[country]
        id_study_name = [study for study in filtered_studies if study.startswith(f'{study_number}_{country_code.lower()}')][0]
        base_path = f'Documentos compartidos/estudios/{id_study_name}'
        folder_url = f'https://connectasas.sharepoint.com/sites/connecta-ciencia_de_datos/Documentos%20compartidos/estudios/{id_study_name}'

        selected_study = list(set([' '.join(study.split('_')[2:]).title() for study in filtered_studies if study.startswith(str(study_number))]))[0]

        st.info(f'Upload to `{selected_study}` study for country: {country}')

        st.subheader('Questionnaire')

        with st.form('upload_questionnaire_form'):
            uploaded_questionnaire = st.file_uploader("Upload `.docx` questionnaire file", type=["docx"], key='questionnaire_docx')
            upload_questionnaire = st.form_submit_button('Upload questionnaire')

        if uploaded_questionnaire and upload_questionnaire:
            questionnaire_path = 'script/cuestionarios'
            files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', questionnaire_path)
            files = [file for file in files if 'Qu' in file]
            if not files:
                file_name = f'{id_study_name}_Qu_V1.docx'
            else:
                last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                file_name = f'{id_study_name}_Qu_V{last_version_number + 1}.docx'

            with st.spinner('Uploading questionnaire to Sharepoint...'):
                upload_file_to_sharepoint(f'{base_path}/{questionnaire_path}', uploaded_questionnaire, file_name)
                st.success(
                    f"Questionnaire uploaded successfully into [study's folder]({folder_url}/{questionnaire_path})."
                )

        st.subheader('Field delivery')

        with st.form('upload_field_delivery_form'):
            uploaded_field_delivery = st.file_uploader("Upload `.docx` field delivery file", type=["docx"], key='field_delivery_docx')
            upload_field_delivery = st.form_submit_button('Upload field delivery')

        if uploaded_field_delivery and upload_field_delivery:
            field_delivery_path = 'script/entrega_campo'
            files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', field_delivery_path)
            files = [file for file in files if 'ECQ' in file]
            if not files:
                file_name = f'{id_study_name}_ECQ_V1.docx'
            else:
                last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                file_name = f'{id_study_name}_ECQ_V{last_version_number + 1}.docx'

            with st.spinner('Uploading field delivery to Sharepoint...'):
                upload_file_to_sharepoint(f'{base_path}/{field_delivery_path}', uploaded_field_delivery, file_name)
                st.success(
                    f"Field delivery uploaded successfully into [study's folder]({folder_url}/{field_delivery_path})."
                )

        st.subheader('Codes book')

        with st.form('upload_codes_book_form'):
            uploaded_codes_book = st.file_uploader("Upload `.xlsx` codes book file", type=["xlsx"], key='codes_book_xlsx')
            upload_codes_book = st.form_submit_button('Upload codes book')

        if uploaded_codes_book and upload_codes_book:
            codes_book_path = 'codificacion/input'
            files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', codes_book_path)
            files = [file for file in files if 'LC' in file]
            if not files:
                file_name = f'{id_study_name}_LC_V1.xlsx'
            else:
                last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                file_name = f'{id_study_name}_LC_V{last_version_number + 1}.xlsx'

            with st.spinner('Uploading codes book to Sharepoint...'):
                upload_file_to_sharepoint(f'{base_path}/{codes_book_path}', uploaded_questionnaire, file_name)
                st.success(
                    f"Codes book uploaded successfully into [study's folder]({folder_url}/{codes_book_path})."
                )

        st.subheader('Processing delivery')

        with st.form('upload_processing_delivery_form'):
            uploaded_processing_delivery = st.file_uploader("Upload `.xlsx` processing delivery file", type=["xlsx"], key='processing_delivery_xlsx')
            upload_processing_delivery = st.form_submit_button('Upload processing delivery')

        if uploaded_processing_delivery and upload_processing_delivery:
            processing_delivery_path = 'generales/input'
            files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', processing_delivery_path)
            files = [file for file in files if 'EPQ' in file]
            if not files:
                file_name = f'{id_study_name}_EPQ_V1.xlsx'
            else:
                last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                file_name = f'{id_study_name}_EPQ_V{last_version_number + 1}.xlsx'

            with st.spinner('Uploading processing delivery to Sharepoint...'):
                upload_file_to_sharepoint(f'{base_path}/{processing_delivery_path}', uploaded_processing_delivery, file_name)
                st.success(
                    f"Processing delivery uploaded successfully into [study's folder]({folder_url}/{processing_delivery_path})."
                )

        st.subheader('Concept')

        with st.form('upload_concept_form'):
            uploaded_concept = st.file_uploader("Upload `.pptx` concept file", type=["pptx"], key='concept_pptx')
            upload_concept = st.form_submit_button('Upload concept')

        if uploaded_concept and upload_concept:
            concept_path = 'script/conceptos'
            files = get_last_file_version_in_sharepoint(id_study_name, 'estudios', concept_path)
            files = [file for file in files if 'EST' in file]
            if not files:
                file_name = f'{id_study_name}_EST_V1.xlsx'
            else:
                last_version_number = max(int(file.split('_')[-1].split('.')[0].replace('V', '')) for file in files)
                file_name = f'{id_study_name}_EST_V{last_version_number + 1}.pptx'

            with st.spinner('Uploading concept to Sharepoint...'):
                upload_file_to_sharepoint(f'{base_path}/{concept_path}', uploaded_concept, file_name)
                st.success(
                    f"Concept uploaded successfully into [study's folder]({folder_url}/{concept_path})."
                )
