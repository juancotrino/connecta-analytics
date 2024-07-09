from io import BytesIO
import tempfile

import re
from itertools import product
import warnings

import numpy as np
import pandas as pd
import pyreadstat

def read_sav_file(filename: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)

        db: pd.DataFrame = pyreadstat.read_sav(
            filename,
            apply_value_formats=False
        )[0]

        metadata = pyreadstat.read_sav(
            filename,
            apply_value_formats=True
        )[1]

    return db, metadata

def get_questions(metadata) -> list[str]:
    # Regular expression pattern to match strings that start with 'P' followed by a digit
    pattern = re.compile(r'^P\d')
    return [question for question in metadata.column_names if pattern.match(question)]

def get_column_labels(metadata, questions: list[str]) -> dict[str, str]:
    return {k: v for k, v in metadata.__dict__['column_names_to_labels'].items() if k in questions}

def get_variable_value_labels(metadata, questions: list[str]) -> dict[str, str]:
    return {k: v for k, v in metadata.__dict__['variable_value_labels'].items() if k in questions}

def get_visits(questions: list[str]) -> list[str]:
    return sorted(list(set([question.split('_')[1] for question in questions])))

def get_samples(questions: list[str]) -> list[str]:
    sample_position = list(set([question.split('_')[2] for question in questions]))
    pattern = re.compile(r'R\d+')
    return list(set([pattern.match(sample).group() for sample in sample_position]))

def get_plain_questions(formatted_questions: list[str]):
    plain_questions = [question.split('_')[0] for question in formatted_questions]
    seen = set()
    return [item for item in plain_questions if not (item in seen or seen.add(item))]

def get_visit_sample_combinations(visits: list[str], samples: list[str]):
    return list(product(visits, samples))

def get_visits_dictionary(visits_names: list[str]) -> dict[str, str]:
    return {k: visit_name for k, visit_name in zip(range(1, len(visits_names) + 1), visits_names)}

def get_samples_dictionary(metadata) -> dict[str, str]:
    return metadata.variable_value_labels['REF.1']

def get_visits_samples_combinations_text(db: pd.DataFrame):
    return list(product(db['REF'].unique().astype(int), db['visit'].unique()))

def assign_sample_visit_code(row: pd.Series, visits_samples_combinations_text: list[tuple[int]]):
    return visits_samples_combinations_text.index((row['REF'], row['visit'])) + 1

def get_sample_visit_value_labels(
    visits_samples_combinations_text: list[tuple[int]],
    samples_dictionary: dict[str, str],
    visits_dictionary: dict[str, str]
):
    sample_visit_value_labels = {}
    for i, (sample, visit) in enumerate(visits_samples_combinations_text):
        sample_visit_value_labels[i + 1] = f'{samples_dictionary[sample]} {visits_dictionary[visit]}'

    return sample_visit_value_labels

def get_column_labels_final(
    metadata,
    questions: list[str],
    question_format_mapping: dict[str, str]
):
    return {question_format_mapping[k].split('_')[0]: v for k, v in metadata.__dict__['column_names_to_labels'].items() if k in questions}

def get_variable_value_labels_final(
    metadata,
    questions: list[str],
    question_format_mapping: dict[str, str]
):
    return {question_format_mapping[k].split('_')[0]: v for k, v in metadata.__dict__['variable_value_labels'].items() if k in questions}

def get_temp_file(file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        tmp_file.write(file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name

def write_temp_sav(df: pd.DataFrame, column_labels: dict[str, str], variable_value_labels: dict[str, str]):
    with tempfile.NamedTemporaryFile() as tmpfile:
        # Write the DataFrame to the temporary SPSS file
        pyreadstat.write_sav(
            df,
            tmpfile.name,
            column_labels=column_labels,
            variable_value_labels=variable_value_labels
        )

        with open(tmpfile.name, 'rb') as f:
            return BytesIO(f.read())


def preprocessing(sav_file: BytesIO, visit_names: list[str]):
    temp_file_name_sav = get_temp_file(sav_file)
    db, metadata = read_sav_file(temp_file_name_sav)

    questions = get_questions(metadata)
    column_labels = get_column_labels(metadata, questions)
    variable_value_labels = get_variable_value_labels(metadata, questions)

    visits = get_visits(questions)
    samples = get_samples(questions)

    if len(visits) != len(visit_names):
        raise AssertionError('Number of visits in database do not match number of visits listed above.')

    # Regular expression to match letters followed by digits
    pattern = r'[A-Za-z]\d*'

    formatted_questions = []

    transformed_column_labels = {}
    transformed_variable_value_labels = {}

    question_format_mapping = {}

    for sample in samples:

        for question in questions:
            reference_field: str = question.split('_')[-1]
            reference_field_list = re.findall(pattern, reference_field)

            if len(reference_field_list) > 1:
                transformed_question_list = question.split('_')[:-1] + reference_field_list
                if len(transformed_question_list) > 3:
                    transformed_question = f"{transformed_question_list[0]}{transformed_question_list[3]}_{transformed_question_list[1]}_{transformed_question_list[2]}"
            else:
                transformed_question = question

            formatted_questions.append(transformed_question)
            transformed_column_labels[transformed_question] = column_labels[question]
            transformed_variable_value_labels[transformed_question] = variable_value_labels[question]

            question_format_mapping[question] = transformed_question

    db = db.rename(columns=question_format_mapping)

    # plain_questions = get_plain_questions(formatted_questions)
    visit_sample_combinations = get_visit_sample_combinations(visits, samples)

    final_rows = []
    for _, row in db.iterrows():
        variable_value = {}

        for visit, sample in visit_sample_combinations:
            visit_sample_questions = [question for question in formatted_questions if question.split('_')[1] == visit and question.split('_')[2] == sample]

            final_row = {
                'Response_ID': row['Response_ID'],
                'visit': int(visit[1:]),
                'REF': row[f'REF.{sample[1:]}']
            }

            for j in visit_sample_questions:
                variable = j.split('_')[0]
                variable_value[variable] = row[j]

            final_row.update(variable_value)

            final_rows.append(final_row)

    visits_dictionary = get_visits_dictionary(visit_names)
    samples_dictionary = get_samples_dictionary(metadata)

    final_db = pd.DataFrame(final_rows)

    visits_samples_combinations_text = get_visits_samples_combinations_text(final_db)

    final_db['visit_sample'] = final_db.apply(
        assign_sample_visit_code,
        visits_samples_combinations_text=visits_samples_combinations_text,
        axis=1
    )

    sample_visit_value_labels = get_sample_visit_value_labels(
        visits_samples_combinations_text,
        samples_dictionary,
        visits_dictionary
    )

    column_labels_final = get_column_labels_final(metadata, questions, question_format_mapping)
    column_labels_final['visit_sample'] = 'visit_sample'

    variable_value_labels_final = get_variable_value_labels_final(metadata, questions, question_format_mapping)
    variable_value_labels_final['visit_sample'] = sample_visit_value_labels

    # Iterate through the unique product references
    unique_samples = final_db['REF'].unique().astype(int)

    for sample in unique_samples:
        # Create a new column for each unique reference
        final_db[samples_dictionary[sample]] = np.where(final_db['REF'] == sample, final_db['visit_sample'], np.nan)
        column_labels_final[samples_dictionary[sample]] = samples_dictionary[sample]
        variable_value_labels_final[samples_dictionary[sample]] = sample_visit_value_labels

    return write_temp_sav(final_db, column_labels_final, variable_value_labels_final)
