import ast
import re

import numpy as np
import pandas as pd
import pyreadstat

def transform_open_ended(questions: pd.DataFrame, df: pd.DataFrame):

    melted_df = df.melt(
        id_vars=[df.columns[0]],
        value_vars=df.columns[1:],
        var_name='question_id',
        value_name='answer'
    )

    melted_df[f'{melted_df.columns[1]}-{melted_df.columns[0]}'] = (
        melted_df[melted_df.columns[1]] + '-' + melted_df[melted_df.columns[0]]
    )


    group_questions_dict = {}
    for i, group in questions.iterrows():
        group_questions = [question.strip() for question in group['questions'].split(',')]
        melted_group_questions = melted_df[melted_df[melted_df.columns[1]].isin(group_questions)]
        melted_group_questions = melted_group_questions[[f'{melted_df.columns[1]}-{melted_df.columns[0]}', melted_df.columns[2]]]
        group_questions_dict['-'.join(group_questions)] = melted_group_questions

    return group_questions_dict

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

    df = df[db.columns.to_list() + numeric_columns + ['ETIQUETAS'] + string_columns]

    return df

def generate_open_ended_db(temp_file_name_xlsx: str, temp_file_name_sav: str):
    dfs = pd.read_excel(temp_file_name_xlsx, sheet_name=None)
    dfs = {k: v for k, v in dfs.items() if 'answers_classified' in k}
    db: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name_sav,
        apply_value_formats=False
    )[0]

    metadata = pyreadstat.read_sav(
        temp_file_name_sav,
        apply_value_formats=False
    )[1]

    df = (
        pd.concat([df for df in dfs.values()])
        .dropna(how='all')
        .dropna(subset='answer_txt')
        .reset_index(drop=True)
    )

    if 'code_ai_micro_txt' in df.columns.to_list():
        df = df.drop(columns='code_ai_micro_txt')

    df['question_code'] = df['respondent_id'].apply(lambda x: x.split('-')[0])
    df['respondent_id'] = df['respondent_id'].apply(lambda x: x.split('-')[1])
    df['question_code_number'] = df['question_code'].apply(lambda x: int(x.split('_')[0][1:]))
    df = df.sort_values(by='question_code_number').reset_index(drop=True)
    df['respondent_id'] = df['respondent_id'].astype(float)
    ordered_questions = df['question_code'].unique().tolist()

    df = df.dropna(subset='code_ai_micro_num')

    df['code_ai_micro_num'] = df['code_ai_micro_num'].apply(lambda x: ast.literal_eval(x) if '[' in x or len(x.split(',')) > 1 else (int(x), ))

    pivoted_df = df.pivot(
        index='respondent_id',
        columns='question_code',
        values=['answer_txt', 'code_ai_micro_num']
    )

    answers: pd.DataFrame = pivoted_df['answer_txt'][ordered_questions]
    answers_codes: pd.DataFrame = pivoted_df['code_ai_micro_num'][ordered_questions]

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
        left_on='Response_ID',
        right_on='respondent_id',
        suffixes=['', 'OT']
    ).drop(columns='respondent_id')

    final_df = reorder_columns(final_df, db)

    return final_df, metadata
