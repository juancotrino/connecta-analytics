from io import BytesIO
import re
import ast
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pyreadstat

from app.modules.cloud import LLM

# Function to expand lists/tuples into columns
def expand_lists(row, max_len):
    if isinstance(row, (list, tuple)):
        return pd.Series(row)
    else:
        return pd.Series([np.nan] * max_len)

def format_time(seconds):
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def extract_json_string(content: str) -> str:
    """Extract JSON-like string from the content."""
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and start <= end:
        return content[start:end + 1]
    return ''

# Custom sort function
def sort_key(item):
    parts = item.split('_')

    # Extract the prefix and number from the question code
    prefix_match = re.match(r"([A-Za-z]+)(\d+)", parts[0])
    if prefix_match:
        prefix = prefix_match.group(1)
        question_number = int(prefix_match.group(2))
    else:
        prefix = parts[0]
        question_number = 0  # Default if no number is found

    # Extract visit number if present
    visit_number = int(parts[1][1:]) if len(parts) > 1 and 'V' in parts[1] else 0

    return (prefix, visit_number, question_number)

def reorder_columns(df: pd.DataFrame, db: pd.DataFrame) -> pd.DataFrame:

    new_columns = df.loc[:, db.columns[-1]:].iloc[:, 1:].columns.to_list()
    new_columns = sorted(new_columns, key=sort_key)

    string_columns = df.select_dtypes(include=['object']).columns.sort_values().tolist()
    string_columns = sorted(string_columns, key=sort_key)

    numeric_columns = [column for column in new_columns if column not in string_columns]

    df['ETIQUETAS'] = np.nan

    df = df[[column for column in db.columns.to_list() if column not in string_columns] + numeric_columns + ['ETIQUETAS'] + string_columns]

    return df

def get_string_columns(db: pd.DataFrame):
    db_string_df = db.select_dtypes(include=['object'])
    db_string_df = db_string_df[db_string_df.columns[
        (db_string_df.columns.str.startswith(('P', 'F'))) &
        ~(db_string_df.columns.str.endswith('O'))
        ]
    ]
    db_string_df = pd.concat([db[['Response_ID']], db_string_df], axis=1)
    return db_string_df

def get_question_groups(db_string_df: pd.DataFrame):
    question_prints = list(set([column.split('_')[0] if column.startswith('P') else column.split('A')[0] for column in db_string_df.columns if column.startswith(('P', 'F'))]))

    question_groups = {}
    for question_print in question_prints:
        question_groups[question_print] = [column for column in db_string_df.columns if column.startswith(question_print)]

    return question_groups

def generate_open_ended_db(results: dict, temp_file_name_sav: str):

    dfs = {question: result['coding_results'] for question, result in results.items()}

    db: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name_sav,
        apply_value_formats=False
    )[0]

    metadata = pyreadstat.read_sav(
        temp_file_name_sav,
        apply_value_formats=False
    )[1]

    db_string_df = get_string_columns(db)

    question_groups = get_question_groups(db_string_df)

    answers_df = transform_open_ended(question_groups, db_string_df)
    total_answers = pd.concat([df for df in answers_df.values()])

    df = (
        pd.concat([df for df in dfs.values()])
        .dropna(how='all')
        .reset_index(drop=True)
    )

    df = df.merge(total_answers[['question_id-Response_ID', 'answer']], on='question_id-Response_ID', how='left')

    df['question_code'] = df['question_id-Response_ID'].apply(lambda x: x.split('-')[0])
    df['Response_ID'] = df['question_id-Response_ID'].apply(lambda x: x.split('-')[1])
    df['question_code_number'] = df['question_code'].apply(lambda x: int(x.split('_')[0][1:]) if '.' not in x.split('_')[0][1:] else float(x.split('_')[0][1:]))
    df = df.sort_values(by='question_code_number').reset_index(drop=True)
    df['Response_ID'] = df['Response_ID'].astype(float)
    df = df.dropna(subset='answer').reset_index(drop=True)

    ordered_questions = df['question_code'].unique().tolist()

    df = df.dropna(subset='codes').reset_index(drop=True)

    pivoted_df = df.pivot(
        index='Response_ID',
        columns='question_code',
        values=['answer', 'codes']
    )

    answers: pd.DataFrame = pivoted_df['answer'][ordered_questions]
    answers_codes: pd.DataFrame = pivoted_df['codes'][ordered_questions]

    # Function to expand lists/tuples into columns
    def expand_lists(row, max_len):
        if isinstance(row, (list, tuple)):
            return pd.Series(row)
        else:
            return pd.Series([np.nan] * max_len)

    for column in answers_codes:
        # Determine the maximum length of lists/tuples
        max_len = answers_codes[column].dropna().apply(len).max()

        # Apply the function and concatenate the results with the original dataframe
        expanded_cols = answers_codes[column].apply(expand_lists, max_len=max_len)
        expanded_cols.columns = [f'{column}A{i + 1}' for i in range(max_len)]
        answers_codes = pd.concat([answers_codes.drop(columns=[column]), expanded_cols], axis=1)

    transformed_df = answers.merge(answers_codes, left_index=True, right_index=True).reset_index()

    final_df = db.merge(
        transformed_df,
        on='Response_ID',
        suffixes=['', 'OT']
    )

    final_df = reorder_columns(final_df, db)
    return final_df, metadata


def transform_open_ended(question_groups: dict[str, list[str]], df: pd.DataFrame):

    df = df.astype(str)

    melted_df = df.melt(
        id_vars=[df.columns[0]],
        value_vars=df.columns[1:],
        var_name='question_id',
        value_name='answer'
    )

    melted_df[f'{melted_df.columns[1]}-{melted_df.columns[0]}'] = (
        melted_df[melted_df.columns[1]] + '-' + melted_df[melted_df.columns[0]]
    )

    question_groups_dict = {}
    for _, question_group in question_groups.items():
        melted_question_groups = melted_df[melted_df[melted_df.columns[1]].isin(question_group)]
        melted_question_groups = melted_question_groups[[f'{melted_df.columns[1]}-{melted_df.columns[0]}', melted_df.columns[2]]]
        question_groups_dict['-'.join(question_group)] = melted_question_groups

    return question_groups_dict

def process_question(question: str, prompt_template: str, answers: dict, code_books: dict):
    print(f'Execution started for question: {question}')

    response_info = {}

    question_answer = [question_answer for question_answer in answers.keys() if question_answer.startswith(question)][0]

    user_prompt = prompt_template.format(
        survey_data={row['question_id-Response_ID']: row['answer'] for _, row in answers[question_answer].iterrows()},
        codebook={row['code_id']: row['code_text'] for _, row in code_books[question].iterrows()}
    )

    llama = LLM()

    response, elapsed_time = llama.send(
        system_prompt='You are a highly skilled NLP model that classifies open ended answers of surveys into categories. You only respond with python dictionary objects.',
        user_prompt=user_prompt
    )

    formatted_time = format_time(elapsed_time)

    if response.status_code != 200:
        raise ValueError(f'Model response unsuccessfull for question: {question} with status code {response.status_code}')

    if response.status_code == 200:
        print(f'Model response successfull for question: {question}')

    response_info['elapsed_time'] = formatted_time

    response_json = response.json()

    response_info['usage'] = response_json['usage']

    coding_dict = response_json['choices'][0]['message']['content'].replace('\\n', '').replace('`', '')

    # Extract and validate the JSON string
    coding_result = extract_json_string(coding_dict)
    if not coding_result:
        print(f"Failed to extract JSON for question {question}")
        response_info['error'] = 'Failed to extract valid JSON'
        response_info['coding_results_raw'] = coding_dict
        return response_info

    try:
        coding_result = ast.literal_eval(coding_dict)
    except:
        response_info['coding_results_raw'] = coding_dict
        return response_info

    coding_df = pd.DataFrame(
        {
            'question_id-Response_ID': coding_result.keys(),
            'codes': coding_result.values()
        }
    )

    response_info['coding_results'] = coding_df

    return response_info

def preprocessing(temp_file_name_xlsx: str, temp_file_name_sav: str):

    code_books = pd.read_excel(temp_file_name_xlsx, sheet_name=None)

    db: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name_sav,
        apply_value_formats=False
    )[0]

    db_string_df = get_string_columns(db)

    question_groups = get_question_groups(db_string_df)

    answers = transform_open_ended(question_groups, db_string_df)

    questions_intersection = list(set(code_books.keys()) & set([question.split('_')[0] for question in answers.keys()]))

    code_books = {k: v.astype(str) for k, v in code_books.items() if k in questions_intersection}
    answers = {k: v.astype(str) for k, v in answers.items() if k.split('_')[0] in questions_intersection}

    for question, code_book in code_books.items():
        code_book = code_book[code_book.columns[:2]]
        code_book = code_book[code_book.iloc[:, 0].str.isdigit()].reset_index(drop=True)
        code_book.columns = ['code_id', 'code_text']
        code_book['code_id'] = code_book['code_id'].astype(int)

        code_books[question] = code_book

    prompt_template = """
        I want you to classify the following survey answers into one or more of the codebook categories.

        Survey Data:
        {survey_data}

        Codebook:
        {codebook}

        Return the classification result as a JSON object where each survey answer is matched with the most appropriate code(s) from the codebook based on the content of the answer. Ensure that the output contains only the JSON result and no additional text.
    """

    results = {}

    # Use ThreadPoolExecutor to parallelize API calls
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {question: executor.submit(process_question, question, prompt_template, answers, code_books) for question in questions_intersection}

        for question, future in futures.items():
            try:
                result = future.result()
                results[question] = result  # Store the result in the dictionary
                print(f"Completed processing for question: {question}")
            except Exception as exc:
                raise ValueError(f"Question {question} generated an exception: {exc}")

    return results
