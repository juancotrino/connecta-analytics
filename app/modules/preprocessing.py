from json import JSONDecoder
import re
import time

# from concurrent.futures import ThreadPoolExecutor
from threading import Thread

import numpy as np
import pandas as pd
import pyreadstat

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx
# from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

from app.cloud import LLM


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


# def extract_json_string(content: str) -> str:
#     """Extract JSON-like string from the content."""
#     start = content.find('{')
#     end = content.rfind('}')
#     if start != -1 and end != -1 and start <= end:
#         return content[start:end + 1]
#     return ''


def extract_json_string(text, decoder=JSONDecoder()):
    """Find JSON objects in text, and return a list of decoded JSON data

    Does not attempt to look for JSON arrays, text, or other JSON types outside
    of a parent JSON object.

    """
    pos = 0
    results = []
    while True:
        match = text.find("{", pos)
        if match == -1:
            break
        try:
            result, index = decoder.raw_decode(text[match:])
            results.append(result)
            pos = match + index
        except ValueError:
            pos = match + 1
    return results


# Custom sort function
def sort_key(item):
    parts = item.split("_")

    # Extract the prefix and number from the question code
    prefix_match = re.match(r"([A-Za-z]+)(\d+)", parts[0])
    if prefix_match:
        prefix = prefix_match.group(1)
        question_number = int(prefix_match.group(2))
    else:
        prefix = parts[0]
        question_number = 0  # Default if no number is found

    # Extract visit number if present
    visit_number = int(parts[1][1:]) if len(parts) > 1 and "V" in parts[1] else 0

    return (prefix, visit_number, question_number)


def reorder_columns(
    df: pd.DataFrame, db: pd.DataFrame, last_num_var=""
) -> pd.DataFrame:
    if last_num_var == "":
        last_num_var = db.columns[-1]
    new_columns = df.loc[:, last_num_var:].iloc[:, 1:].columns.to_list()
    new_columns = sorted(new_columns, key=sort_key)

    string_columns = df.select_dtypes(include=["object"]).columns.sort_values().tolist()
    string_columns = sorted(string_columns, key=sort_key)

    open_ended_code_columns = [
        column for column in new_columns if column not in string_columns
    ]

    df["ETIQUETAS"] = np.nan
    df["ABIERTAS"] = np.nan

    df = df[
        [column for column in db.columns.to_list() if column not in string_columns]
        + ["ABIERTAS"]
        + open_ended_code_columns
        + ["ETIQUETAS"]
        + string_columns
    ]

    return df


def get_string_columns(db: pd.DataFrame):
    db_string_df = db.select_dtypes(include=["object"])
    db_string_df = db_string_df[
        db_string_df.columns[db_string_df.columns.str.startswith(("P", "F"))]
    ]
    db_string_df = pd.concat([db[["Response_ID"]], db_string_df], axis=1)
    return db_string_df


def get_question_groups(question_prints: list[str], db_string_df: pd.DataFrame):
    question_groups = {}
    for question_print in question_prints:
        question_groups[question_print] = [
            column
            for column in db_string_df.columns
            if column.split("_")[0] == question_print
        ]

    return question_groups


def generate_open_ended_db(results: dict, temp_file_name_sav: str):
    dfs = {
        question: result["coding_results"]
        for question, result in results.items()
        if not result["coding_results"].empty
    }

    db: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name_sav, apply_value_formats=False
    )[0]

    metadata = pyreadstat.read_sav(temp_file_name_sav, apply_value_formats=False)[1]

    db_string_df = get_string_columns(db)

    question_groups = get_question_groups(dfs.keys(), db_string_df)

    answers_df = transform_open_ended(question_groups, db_string_df)
    total_answers = pd.concat([df for df in answers_df.values()])

    df = pd.concat([df for df in dfs.values()]).dropna(how="all").reset_index(drop=True)

    df = df.merge(
        total_answers[["question_id-Response_ID", "answer"]],
        on="question_id-Response_ID",
        how="left",
    )

    df["question_code"] = df["question_id-Response_ID"].apply(lambda x: x.split("-")[0])
    df["Response_ID"] = df["question_id-Response_ID"].apply(lambda x: x.split("-")[1])
    df["question_code_number"] = df["question_code"].apply(
        lambda x: int(x.split("_")[0][1:])
        if "." not in x.split("_")[0][1:]
        else float(x.split("_")[0][1:])
    )
    df = df.sort_values(by="question_code_number").reset_index(drop=True)
    df["Response_ID"] = df["Response_ID"].astype(float)
    df = df.dropna(subset="answer").reset_index(drop=True)

    ordered_questions = df["question_code"].unique().tolist()

    df = (
        df.dropna(subset="codes")
        .drop_duplicates(subset=["question_code", "Response_ID"])
        .reset_index(drop=True)
    )

    pivoted_df = df.pivot(
        index="Response_ID", columns="question_code", values=["answer", "codes"]
    )

    answers: pd.DataFrame = pivoted_df["answer"][ordered_questions]
    answers_codes: pd.DataFrame = pivoted_df["codes"][ordered_questions]

    # Function to expand lists/tuples into columns
    def expand_lists(row, max_len):
        if isinstance(row, (list, tuple)):
            return pd.Series(row)
        else:
            return pd.Series([np.nan] * max_len)

    expanded_answers_codes_list = []

    for column in answers_codes:
        # Determine the maximum length of lists/tuples
        max_len = answers_codes[column].dropna().apply(len).max()

        # Apply the function and concatenate the results with the original dataframe
        expanded_cols = answers_codes[column].apply(expand_lists, max_len=max_len)
        expanded_cols.columns = [f"{column}A{i + 1}" for i in range(max_len)]
        expanded_answers_codes_list.append(expanded_cols)

    expanded_answers_codes = pd.concat(expanded_answers_codes_list, axis=1)

    transformed_df = answers.merge(
        expanded_answers_codes, left_index=True, right_index=True
    ).reset_index()

    final_df = db.merge(
        transformed_df, on="Response_ID", suffixes=["", "_right"], how="left"
    )
    final_df = final_df.drop(
        columns=[col for col in final_df.columns if col.endswith("_right")]
    )

    final_df = reorder_columns(final_df, db)
    return final_df, metadata


def transform_open_ended(question_groups: dict[str, list[str]], df: pd.DataFrame):
    df = df.astype(str)

    melted_df = df.melt(
        id_vars=[df.columns[0]],
        value_vars=df.columns[1:],
        var_name="question_id",
        value_name="answer",
    )

    melted_df = melted_df[melted_df["answer"] != ""].reset_index(drop=True)

    melted_df[f"{melted_df.columns[1]}-{melted_df.columns[0]}"] = (
        melted_df[melted_df.columns[1]] + "-" + melted_df[melted_df.columns[0]]
    )

    question_groups_dict = {}
    for _, question_group in question_groups.items():
        melted_question_groups = melted_df[
            melted_df[melted_df.columns[1]].isin(question_group)
        ]
        melted_question_groups = melted_question_groups[
            [f"{melted_df.columns[1]}-{melted_df.columns[0]}", melted_df.columns[2]]
        ]
        question_groups_dict["-".join(question_group)] = melted_question_groups

    return question_groups_dict


def calculate_timeout(num_answers, base_time=50, rate=2.25):
    """
    Calculate timeout based on the number of answers.

    :param num_answers: Number of answers to be processed.
    :param base_time: Base time in seconds (overhead), default is 50 seconds.
    :param rate: Time per answer in seconds, default is 2.25 seconds/answer.
    :return: Calculated timeout in seconds.
    """
    return base_time + (num_answers * rate)


def process_question(
    question: str,
    prompt_template: str,
    answers: dict,
    code_books: dict,
    model: LLM,
    ui_container,
    results: dict,
):
    ui_container.info(f"Coding question: `{question}`")

    response_info = {}
    try:
        question_answer = [
            question_answer
            for question_answer in answers.keys()
            if question_answer.split("_")[0] == question
        ][0]
    except Exception as e:
        ui_container.error(f"Error in format question `{question}`: {e}")

    if answers[question_answer].empty:
        ui_container.warning(f"No answers to code for question: `{question}`")
        return {
            "coding_results": pd.DataFrame(),
            "status_code": None,
            "elapsed_time": None,
            "usage": None,
            "retries": None,
        }

    user_prompt = prompt_template.format(
        survey_data={
            row["question_id-Response_ID"]: row["answer"]
            for _, row in answers[question_answer].iterrows()
        },
        codebook={
            row["code_id"]: row["code_text"]
            for _, row in code_books[question].iterrows()
        },
    )
    timeout = calculate_timeout(len(answers[question_answer]))

    st.info(f"Coding question `{question}`")
    try:
        start_time = time.time()
        response, retries = model.send(
            system_prompt="You are a highly skilled NLP model that classifies open ended answers of surveys into categories. You only respond with python dictionary objects.",
            user_prompt=user_prompt,
            timeout=timeout,
        )
    except Exception as e:
        ui_container.error(f"Error in request for question `{question}`: {e}")

    end_time = time.time()
    elapsed_time = end_time - start_time

    formatted_time = format_time(elapsed_time)

    response_json = response.json()

    response_info["status_code"] = response.status_code
    response_info["retries"] = retries

    if response.status_code != 200:
        ui_container.error(
            f"Model response unsuccessfull for question: `{question}` with status code {response.status_code}. JSON response: {response_json}"
        )
        raise ValueError(
            f"Model response unsuccessfull for question: `{question}` with status code {response.status_code}. JSON response: {response_json}"
        )

    response_info["elapsed_time"] = formatted_time

    response_info["usage"] = response_json["usage"]

    coding_dict = (
        response_json["choices"][0]["message"]["content"]
        .replace("json", "")
        .replace("\\n", "")
        .replace("`", "")
        .replace("'", '"')
    )

    try:
        # Extract and validate the JSON string
        coding_result = extract_json_string(coding_dict)[0]

        if not coding_result:
            print(f"Failed to extract JSON for question {question}")
            response_info["error"] = "Failed to extract valid JSON"
            response_info["coding_results_raw"] = coding_dict
            # ui_container.write(response_info['coding_results_raw'])
            return response_info

    except Exception as e:
        response_info["coding_results_raw"] = coding_dict
        # with open(f"coding_dict_raw_{question}.txt", "w") as file:
        #     file.write(coding_dict)
        ui_container.error(
            f"Error parsing Llama response to JSON for question `{question}`: {e}"
        )
        ui_container.write(coding_dict)
        return response_info

    coding_df = pd.DataFrame(
        {
            "question_id-Response_ID": coding_result.keys(),
            "codes": coding_result.values(),
        }
    )

    # Check if the column 'A' is of type int
    if pd.api.types.is_integer_dtype(coding_df["codes"]):
        # Replace each integer in the column with a list containing that integer
        coding_df["codes"] = coding_df["codes"].apply(lambda x: [x])

    response_info["coding_results"] = coding_df

    results[question] = response_info

    ui_container.success(f"Model response successfull for question: `{question}`")

    # return response_info


def preprocessing(temp_file_name_xlsx: str, temp_file_name_sav: str):
    code_books = pd.read_excel(temp_file_name_xlsx, sheet_name=None)
    questions = code_books.keys()

    db: pd.DataFrame = pyreadstat.read_sav(
        temp_file_name_sav, apply_value_formats=False
    )[0]

    db_string_df = get_string_columns(db)

    question_groups = get_question_groups(questions, db_string_df)

    answers = transform_open_ended(question_groups, db_string_df)

    for question, code_book in code_books.items():
        code_book = code_book[code_book.columns[:2]]
        code_book = code_book[
            code_book.iloc[:, 0].astype(str).str.strip().str.isdigit()
        ].reset_index(drop=True)
        code_book.columns = ["code_id", "code_text"]
        code_book["code_id"] = code_book["code_id"].astype(int)
        code_book["code_text"] = code_book["code_text"].str.strip()

        code_books[question] = code_book

    prompt_template = """
        I want you to classify the following survey answers into one or more of the codebook categories.

        Survey Data:
        {survey_data}

        Codebook:
        {codebook}

        Return the classification result as a JSON object where each survey answer is matched with the most appropriate code(s) in a list from the codebook based on the content of the answer. Ensure that the output contains only the JSON result and no additional text or characters outside the JSONs curly braces.
    """

    model = LLM()

    results = {}

    threads = []
    containers = []
    for question in questions:
        ui_container = st.empty()  # Create an empty placeholder for each thread
        containers.append(ui_container)
        t = Thread(
            target=process_question,
            args=(
                question,
                prompt_template,
                answers,
                code_books,
                model,
                ui_container,
                results,
            ),
        )
        add_script_run_ctx(t)  # Necessary for Streamlit to track the thread context
        threads.append(t)
        try:
            t.start()
            # time.sleep(0.5)
        except Exception as e:
            st.error(f"Question {question} generated an exception: {e}")
            raise ValueError(f"Question {question} generated an exception: {e}")
    for t in threads:
        t.join()  # Wait for all threads to finish before continuing

    return results
