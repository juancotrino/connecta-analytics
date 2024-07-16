from io import BytesIO
import tempfile

import numpy as np
import pandas as pd
import pyreadstat

from firebase_admin import firestore

import streamlit as st

from app.modules.cloud import SharePoint, BigQueryClient

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

def write_df_bytes(df: pd.DataFrame):
    # Use a context manager with BytesIO
    bytes_io = BytesIO()

    # Save the DataFrame to the BytesIO object as a CSV
    df.to_excel(bytes_io, index=False)

    # Reset the buffer's position to the beginning
    bytes_io.seek(0)

    return bytes_io

def write_txt_bytes(text: str):

    # Create a BytesIO object
    output = BytesIO()

    # Write the combined output to the BytesIO object
    output.write(text.encode('utf-8'))

    # Seek to the beginning of the BytesIO object to read its content from the start
    output.seek(0)

    return output

# def write_temp_txt(text: str):
#     with tempfile.NamedTemporaryFile() as tmpfile:


#         # Write the markdown output to a txt file
#         with open(tmpfile.name, 'w') as file:
#             file.write(text)

#         with open(tmpfile.name, 'rb') as f:
#             return BytesIO(f.read())

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

def get_scales_data(study_number: int, study_data: pd.DataFrame, metadata):

    scales_data_list = [
        pd.DataFrame(
            {
                'study_number': [study_number] * len(labels),
                'question_code': [variable] * len(labels),
                'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
                'answer_code': list(labels.keys()),
                'answer_label': list(labels.values()),
                'is_inverted': list(study_data[study_data['question_code'] == variable.split('.')[0]]['is_inverted'].values) * len(labels),
                'jr_option': list(study_data[study_data['question_code'] == variable.split('.')[0]]['jr_option'].values) * len(labels),
            }
        ) for variable, labels in metadata.variable_value_labels.items()
        if (
            (
                len(variable.split('.')) > 0
                and variable.split('.')[0] in study_data['question_code'].tolist()
            ) or (
                variable in study_data['question_code'].tolist()
            )
        ) and (
            'justo' not in ' '.join(labels.values()).lower()
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

def get_jr_scales_data(study_number: int, study_data: pd.DataFrame, metadata):

    jr_scales_data_list = [
        pd.DataFrame(
            {
                'study_number': [study_number] * len(labels),
                'question_code': [variable] * len(labels),
                'question': list(study_data[study_data['question_code'] == variable.split('.')[0]]['question'].values) * len(labels),
                'answer_code': list(labels.keys()),
                'answer_label': list(labels.values()),
                'is_inverted': list(study_data[study_data['question_code'] == variable.split('.')[0]]['is_inverted'].values) * len(labels),
                'jr_option': list(study_data[study_data['question_code'] == variable.split('.')[0]]['jr_option'].values) * len(labels),
            }
        ) for variable, labels in metadata.variable_value_labels.items()
        if (
            (
                len(variable.split('.')) > 0
                and variable.split('.')[0] in study_data['question_code'].tolist()
            ) or (
                variable in study_data['question_code'].tolist()
            )
        ) and (
            'justo' in ' '.join(labels.values()).lower()
        )
    ]

    if jr_scales_data_list:

        jr_scales_data = pd.concat(jr_scales_data_list).reset_index(drop=True)

        count_jr_scales_data = jr_scales_data.groupby(['study_number', 'question_code', 'question']).count()
        unique_count_jr_scales_data = count_jr_scales_data.reset_index()['answer_code'].unique()
        print(f'Unique values of answer options length for JR questions (should only be 5 or 3): {", ".join(unique_count_jr_scales_data.astype(str))}')

        jr_scales_data['is_inverted'] = np.where(~jr_scales_data['jr_option'].isna(), True, False)
        jr_scales_data['real_value'] = np.where(
            jr_scales_data['jr_option'] == jr_scales_data['answer_code'],
            3,
            np.where(
                jr_scales_data['is_inverted'] == False,
                jr_scales_data['answer_code'],
                1
            )
        ).astype(int)

        return jr_scales_data

def assign_real_values(df: pd.DataFrame, real_value_df: pd.DataFrame | None):

    if real_value_df is None:
        return df

    final_columns = df.columns
    df = df.merge(
        real_value_df[['question', 'answer_code', 'real_value']],
        left_on=['attribute', 'value'],
        right_on=['question', 'answer_code'],
        how='left'
    )

    df['value'] = np.where(
        df['value'] == df['answer_code'],
        df['real_value'],
        df['value']
    ).astype(int)

    df = df[final_columns]

    return df

def get_logs(study_info: dict):

    logs_demographics_df = pd.DataFrame(
        {
            'study_number': [study_info['study_id']],
            'study_name': [study_info['study_name']],
            'country': [study_info['country']],
            'client': [study_info['client']],
            'category': [study_info['category']],
            'sub_category': [study_info['sub_category']],
            'brand': [study_info['brand']],
        }
    ).transpose().reset_index()

    logs_demographics_df.columns = ['variable', 'value']

    logs_variable_mapping_df: pd.DataFrame = study_info['variables_mapping']

    logs_demographics = logs_demographics_df.to_markdown(headers='keys', tablefmt='psql', index=False)
    logs_variable_mapping = logs_variable_mapping_df.to_markdown(headers='keys', tablefmt='psql', index=False)

    logs = "DEMOGRAPHICS:\n\n" + logs_demographics + "\n\n\nVARIABLE MAPPING:\n\n" + logs_variable_mapping

    return write_txt_bytes(logs)

def transponse_df(df: pd.DataFrame):

    transformed_data = df.melt(
        id_vars=df.columns[:14].tolist(),
        value_vars=df.columns[14:].tolist(),
        var_name='attribute',
        value_name='value'
    ).dropna(subset='value').reset_index(drop=True)

    transformed_data['category'] = transformed_data['category'].apply(lambda x: x.strip())
    # transformed_data['gender'] = transformed_data['gender'].astype(str)
    transformed_data['age'] = transformed_data['age'].apply(lambda x: x if isinstance(x, (float, int)) else np.nan)
    # transformed_data['ses'] = transformed_data['ses'].astype(str)
    transformed_data['country'] = transformed_data['country'].apply(lambda x: x.title())
    transformed_data['study_number'] = transformed_data['study_number'].astype(int)
    transformed_data['age'] = transformed_data['age'].astype(int)
    # transformed_data['sub_category'] = transformed_data['sub_category'].astype(str)
    transformed_data['value'] = transformed_data['value'].astype(int)

    return transformed_data

def check_project_existance_in_bq(project_id: int):
    bq = BigQueryClient()
    bq.fetch_data(
        """
        SELECT 1
        FROM `connecta-analytics-app.normas.noel`
        WHERE unique_key = value;
        """
    )
    pass

def load_to_bq(df: pd.DataFrame):
    bq = BigQueryClient()
    bq.load_data('noel', df)

def process_study(spss_file_name: str, study_info: dict):

    study_number = study_info['study_id']
    study_name = study_info['study_name']
    study_data: pd.DataFrame = study_info['variables_mapping']
    country = study_info['country']
    client = study_info['client']
    category = study_info['category']
    sub_category = study_info['sub_category']
    brand = study_info['brand']
    demographic_variables = study_info['demographic_variables']
    final_columns = study_info['db_variables']

    metadata = pyreadstat.read_sav(
        spss_file_name,
        apply_value_formats=False
    )[1]

    final_data_template = pd.DataFrame(columns=final_columns)

    print(f'Processing study {study_number}_{study_name}...')

    survey_data_tags: pd.DataFrame = pyreadstat.read_sav(
        spss_file_name,
        apply_value_formats=True
    )[0].dropna(how='all')

    survey_data: pd.DataFrame = pyreadstat.read_sav(
        spss_file_name,
        apply_value_formats=False
    )[0].dropna(how='all')

    scales_data = get_scales_data(study_number, study_data, metadata)
    jr_scales_data = get_jr_scales_data(study_number, study_data, metadata)

    # print('scales_data', scales_data, sep='\n')
    # print('jr_scales_data', jr_scales_data, sep='\n')

    demographic_variables_codes = study_data[study_data['question'].isin(demographic_variables)]['question_code'].to_list()

    pattern = study_info['sample_variable']

    sample_columns = survey_data[survey_data.columns[survey_data.columns.str.contains(pattern, regex=True)]].columns.tolist()

    survey_data.loc[:, demographic_variables_codes + sample_columns] = survey_data_tags.loc[:, demographic_variables_codes + sample_columns]

    if 'sys_RespNum' not in study_data['question'].to_list():
        survey_data = survey_data.reset_index(names='sys_RespNum')

    survey_data = survey_data.replace({'': np.nan})
    survey_data = survey_data.replace({-99: np.nan})

    print(f'Number of surveys taken: {len(survey_data)}')

    for _, survey in survey_data.iterrows():
        # print(f'Processing survey {_}')
        answers = survey.to_frame(name='answer').reset_index(names='question_code')

        test_samples_nan = (
            answers['question_code']
            .apply(
                lambda x: x.split('.')[1]
                if (
                    len(x.split('.')) > 1
                    and '_' not in x.split('.')[1]
                    and (
                        'P' in x.split('.')[0]
                        or 'p' in x.split('.')[0]
                        or 'N' in x.split('.')[0]
                    )
                ) else np.nan
            )
            .astype(float)
            .isna()
        )

        if len(sample_columns) > 1 and all(test_samples_nan):
            print('Inconsistency: There is more than one sample but there are no variables with pattern PXX.X or pXX.X or NXX.X')
            break

        if all(test_samples_nan):
            answers['sample_number'] = 1

            answers['question_code'] = (
                answers['question_code']
                .apply(lambda x: x.split('.')[0] if len(x.split('.')) > 1 else x)
            )

            samples = pd.DataFrame(
                {
                    'question_code': [1],
                    'sample': answers[answers['question_code'].str.contains(pattern)]['answer'].values,
                    'sample_number': [1]
                }
            )

        else:
            answers['sample_number'] = (
                answers['question_code']
                .apply(
                    lambda x: x.split('.')[1]
                    if (
                        len(x.split('.')) > 1
                        and '_' not in x.split('.')[1]
                        and (
                            'P' in x.split('.')[0]
                            or 'p' in x.split('.')[0]
                            or 'N' in x.split('.')[0]
                        )
                    ) else np.nan
                )
                .astype(float)
            )

            answers['question_code'] = (
                answers['question_code']
                .apply(lambda x: x.split('.')[0] if len(x.split('.')) > 1 else x)
            )

            answers['sample_number'] = np.where(
                answers['question_code'].isin(study_data['question_code']), answers['sample_number'], np.nan
            )

            test_samples_nan = (
                answers['sample_number']
                .isna()
            )

            if len(sample_columns) > 1 and all(test_samples_nan):
                print('Inconsistency: (Second instance) There is more than one sample but there are no variables with pattern PXX.X or pXX.X or NXX.X')
                break

            if all(test_samples_nan):
                answers['sample_number'] = 1

                answers['question_code'] = (
                    answers['question_code']
                    .apply(lambda x: x.split('.')[0] if len(x.split('.')) > 1 else x)
                )

                samples = pd.DataFrame(
                    {
                        'question_code': [1],
                        'sample': [1],
                        'sample_number': [1]
                    }
                )


            # Get samples of this survey
            samples = answers[answers['question_code'].str.contains(pattern, regex=True)].reset_index(drop=True).replace({0: np.nan})
            samples = samples[~samples['answer'].isna()].reset_index(drop=True)
            samples['sample_number'] = answers[(~answers['sample_number'].isna()) & (~answers['answer'].isna())]['sample_number'].unique().astype(int)
            samples = samples.rename(columns={'answer': 'sample'})

        answers_merged = (
            study_data.merge(answers, on='question_code')
            .dropna(subset='answer')
            .reset_index(drop=True)
        )

        questions_with_sample = answers_merged[~answers_merged['sample_number'].isna()].reset_index(drop=True)
        questions_without_sample = answers_merged[answers_merged['sample_number'].isna()].reset_index(drop=True)

        questions_without_sample_duplication = []
        for sample in answers_merged['sample_number'].dropna().unique():
            df_sample = questions_without_sample.copy()
            df_sample['sample_number'] = sample
            questions_without_sample_duplication.append(df_sample)

        questions_answers_merged = (
            pd.concat(questions_without_sample_duplication + [questions_with_sample])
            .drop_duplicates()
            .reset_index(drop=True)
        )

        pivoted_answers = (
            questions_answers_merged
            .drop(columns='question_code')
            .pivot(
                columns='question',
                index='sample_number',
                values='answer'
            )
            .reset_index()
        )

        pivoted_answers['sample_number'] = pivoted_answers['sample_number'].astype(int)

        pivoted_answers = samples.drop(columns='question_code').merge(pivoted_answers, on='sample_number')

        # Fill static information
        pivoted_answers['study_number'] = study_number
        pivoted_answers['study_name'] = study_name
        pivoted_answers['category'] = category
        pivoted_answers['sub_category'] = sub_category
        pivoted_answers['sys_RespNum'] = answers[answers['question_code'] == 'sys_RespNum'].reset_index(drop=True)['answer'].astype(int).loc[0]
        pivoted_answers['country'] = country
        pivoted_answers['client'] = client
        pivoted_answers['brand'] = brand

        final_data_template = pd.concat([final_data_template, pivoted_answers]).reset_index(drop=True)

    final_data_template = final_data_template[list(final_columns)]

    final_data_template = transponse_df(final_data_template)

    final_data_template = assign_real_values(final_data_template, scales_data)
    final_data_template = assign_real_values(final_data_template, jr_scales_data)

    final_data_template = final_data_template.replace({np.nan: None})

    load_to_bq(final_data_template)

    return write_df_bytes(final_data_template)
