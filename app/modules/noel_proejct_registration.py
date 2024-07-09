from io import BytesIO
import tempfile

import pandas as pd
import pyreadstat

from firebase_admin import firestore

import streamlit as st

from app.modules.cloud import SharePoint

def get_temp_file(spss_file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(spss_file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name

def read_sav_metadata(file_name: str) -> pd.DataFrame:
    metadata =  pyreadstat.read_sav(
        file_name,
        apply_value_formats=False
    )[1]

    variable_info = pd.DataFrame([metadata.column_names_to_labels, metadata.variable_value_labels])
    variable_info = variable_info.transpose()
    variable_info.index.name = 'name'
    variable_info.columns = ('label', 'values')
    variable_info = variable_info.replace({None: ''})
    variable_info['label'] = variable_info['label'].astype(str)
    variable_info['values'] = variable_info['values'].astype(str)

    return variable_info

@st.cache_data(show_spinner=False)
def get_projects_info():
    db = firestore.client()
    document = db.collection("settings").document('projects_info').get()

    if document.exists:
        projects_info = document.to_dict()
        return projects_info

def create_folder_structure(base_path: str):
    sharepoint = SharePoint()

    studies_in_sharepoint = sharepoint.list_folders('Documentos compartidos/estudios_externos')

    id_project_name = base_path.split('/')[-1]
    if id_project_name in studies_in_sharepoint:
        raise NameError('Combination of ID, country and study name alreday exists.')

    sharepoint.create_folder(base_path)

def upload_file_to_sharepoint(base_path: str, file_content: BytesIO, file_name: str):
    sharepoint = SharePoint()

    sharepoint.upload_file(base_path, file_content, file_name)

def variables_validation(selected_variables: dict, metadata_df: pd.DataFrame):
    # Check for missing values
    missing_values = {k: v for k, v in selected_variables.items() if v not in metadata_df.index.values}
    if missing_values:
        missing_str = ", ".join([f"{k}: {v}" for k, v in missing_values.items()])
        raise ValueError(f"Missing variables in database: {missing_str}")

def metadata_validation(metadata_df: pd.DataFrame):
    if metadata_df.empty:
        raise ValueError("Database file has no metadata")

def duplicated_variables_validation(selected_variables: dict):
    # Convert dictionary values to a DataFrame
    df = pd.DataFrame(list(selected_variables.values()), columns=['Values'])

    # Check for duplicate values
    duplicates = df[df.duplicated()]

    # Print duplicate values
    if not duplicates.empty:
        raise ValueError(f"Duplicate Values: {', '.join(duplicates['Values'].values)}")

# Validation function
def validate_data(selected_variables: dict, metadata_df: pd.DataFrame):
    variables_validation(selected_variables, metadata_df)
    metadata_validation(metadata_df)
    duplicated_variables_validation(selected_variables)

def process_project(spss_file_name: str):
    pass
    # scales_data = pd.DataFrame(
    #     columns=['study_number', 'file_name', 'question_code', 'question', 'answer_code', 'answer_label']
    # )

    # jr_scales_data = pd.DataFrame(
    #     columns=['study_number', 'file_name', 'question_code', 'question', 'answer_code', 'answer_label']
    # )


    # study_data = study[~study.isna()].to_frame(name='question_code').reset_index(names='question')
    # study_data['question_code'] = study_data['question_code'].apply(lambda x: x.split(',')[0].strip() if isinstance(x, str) else x)
    # study_number = str(study['Número del estudio'])

    # if not duplicated_question_codes.empty and study_number in duplicated_question_codes['study_number'].unique().astype(str):
    #     return None

    # file_name = study_data[study_data['question'] == 'Nombre de archivo']['question_code'].values[0]

    # if file_name is None:
    #     print(f'\tThere is no .sav for Study number: {study_number}')
    #     return None
    # survey_data = pyreadstat.read_sav(
    #     f'data/{file_name}.sav',
    #     apply_value_formats=False
    # )[1]

    # for variable, labels in survey_data.variable_value_labels.items():
    #     if (
    #         (
    #             len(variable.split('.')) > 0
    #             and variable.split('.')[0] in study_data[15:]['question_code'].tolist()
    #         ) or (
    #             variable in study_data[15:]['question_code'].tolist()
    #         )
    #     ) and (
    #         'just' not in ' '.join(labels.values()).lower()
    #     ):
    #         scales_data = pd.concat(
    #             [
    #                 scales_data,
    #                 pd.DataFrame(
    #                     {
    #                         'study_number': [int(study_number)] * len(labels),
    #                         'file_name': [file_name] * len(labels),
    #                         'question_code': [variable] * len(labels),
    #                         'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
    #                         'answer_code': list(labels.keys()),
    #                         'answer_label': list(labels.values())
    #                     }
    #                 )
    #             ]
    #         ).reset_index(drop=True)


    # for variable, labels in survey_data.variable_value_labels.items():
    #     if (
    #         (
    #             len(variable.split('.')) > 0
    #             and variable.split('.')[0] in study_data[15:]['question_code'].tolist()
    #         ) or (
    #             variable in study_data[15:]['question_code'].tolist()
    #         )
    #     ) and (
    #         'just' in ' '.join(labels.values()).lower()
    #     ):
    #         jr_scales_data = pd.concat(
    #             [
    #                 jr_scales_data,
    #                 pd.DataFrame(
    #                     {
    #                         'study_number': [int(study_number)] * len(labels),
    #                         'file_name': [file_name] * len(labels),
    #                         'question_code': [variable] * len(labels),
    #                         'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
    #                         'answer_code': list(labels.keys()),
    #                         'answer_label': list(labels.values())
    #                     }
    #                 )
    #             ]
    #         ).reset_index(drop=True)
