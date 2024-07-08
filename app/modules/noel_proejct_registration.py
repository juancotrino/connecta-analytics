from io import BytesIO
import tempfile

import numpy as np
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
def get_studies_info():
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
    missing_values = {k: v for k, v in selected_variables.items() if v not in [value.split('.')[0] for value in metadata_df.index.values]}
    print(missing_values)
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

def get_scales_data(study_number: int, study_data: pd.DataFrame, survey_data):

    scales_data_list = [
        pd.DataFrame(
            {
                'study_number': [study_number] * len(labels),
                'question_code': [variable] * len(labels),
                'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
                'answer_code': list(labels.keys()),
                'answer_label': list(labels.values()),
                'is_inverted': list(study_data[study_data['question_code'] == variable.split('.')[0]]['is_inverted'].values) * len(labels),
            }
        ) for variable, labels in survey_data.variable_value_labels.items()
        if (
            (
                len(variable.split('.')) > 0
                and variable.split('.')[0] in study_data['question_code'].tolist()
            ) or (
                variable in study_data['question_code'].tolist()
            )
        ) and (
            'just' not in ' '.join(labels.values()).lower()
        )
    ]

    if scales_data_list:

        scales_data = pd.concat(scales_data_list).reset_index(drop=True)

        count_scales_data = scales_data.groupby(['study_number', 'question_code', 'question']).count()
        unique_count_scales_data = count_scales_data.reset_index()['answer_code'].unique()
        print(f'Unique values of answer options length for regular questions (should only be 5): {", ".join(unique_count_scales_data.astype(str))}')

        inverted_template = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}

        scales_data['real_value'] = np.where(
            scales_data['is_inverted'] == True,
            scales_data['answer_code'].map(inverted_template),
            scales_data['answer_code']
        )

        return scales_data

def get_jr_scales_data(study_number: int, study_data: pd.DataFrame, survey_data):

    jr_scales_data_list = [
        pd.DataFrame(
            {
                'study_number': [study_number] * len(labels),
                'question_code': [variable] * len(labels),
                'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
                'answer_code': list(labels.keys()),
                'answer_label': list(labels.values()),
                'is_inverted': list(study_data[study_data['question_code'] == variable.split('.')[0]]['is_inverted'].values) * len(labels),
            }
        ) for variable, labels in survey_data.variable_value_labels.items()
        if (
            (
                len(variable.split('.')) > 0
                and variable.split('.')[0] in study_data[15:]['question_code'].tolist()
            ) or (
                variable in study_data[15:]['question_code'].tolist()
            )
        ) and (
            'just' in ' '.join(labels.values()).lower()
        )
    ]

    if jr_scales_data_list:

        jr_scales_data = pd.concat(jr_scales_data_list).reset_index(drop=True)

        count_jr_scales_data = jr_scales_data.groupby(['study_number', 'question_code', 'question']).count()
        unique_count_jr_scales_data = count_jr_scales_data.reset_index()['answer_code'].unique()
        print(f'Unique values of answer options length for JR questions (should only be 5 or 3): {", ".join(unique_count_jr_scales_data.astype(str))}')

        inverted_template = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}

        jr_scales_data['real_value'] = np.where(
            jr_scales_data['is_inverted'] == True,
            jr_scales_data['answer_code'].map(inverted_template),
            jr_scales_data['answer_code']
        )

        return jr_scales_data

def process_study(spss_file_name: str, study_info: dict):

    study_number = study_info['study_id']
    study_data = study_info['variables_mapping']

    survey_data = pyreadstat.read_sav(
        spss_file_name,
        apply_value_formats=False
    )[1]

    scales_data = get_scales_data(study_number, study_data, survey_data)
    jr_scales_data = get_jr_scales_data(study_number, study_data, survey_data)

    print('scales_data:\n', scales_data)
    print('jr_scales_data:\n', jr_scales_data)
