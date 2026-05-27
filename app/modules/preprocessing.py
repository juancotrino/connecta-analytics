from json import JSONDecoder
import os
import random
import sys
import re
import time
from queue import Empty, Queue

# from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore, Thread

import numpy as np
import pandas as pd
import pyreadstat

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx
# from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

from app.cloud import LLM
import google.cloud.logging
import logging

client = google.cloud.logging.Client()
client.setup_logging()

logger = logging.getLogger(__name__)
# Add console output
if not any(
    isinstance(handler, logging.StreamHandler)
    and getattr(handler, "stream", None) is sys.stdout
    for handler in logger.handlers
):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


LOG_LLM_IO = _env_flag("PREPROCESSING_LOG_LLM_IO", "true")


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
        lambda x: (
            int(x.split("_")[0][1:])
            if "." not in x.split("_")[0][1:]
            else float(x.split("_")[0][1:])
        )
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


def remove_chain_of_thought(text: str) -> str:
    """
    Removes <think>...</think> blocks from model output.
    Works even if there are multiple blocks.
    """
    if not text:
        return text

    # Remove everything between <think>...</think>
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    return cleaned.strip()


def process_question(
    question: str,
    prompt_template: str,
    answers: dict,
    code_books: dict,
    model: LLM,
    ui_container,
    results: dict,
):
    def notify(level: str, message: str):
        if ui_container is not None:
            getattr(ui_container, level)(message)

    notify("info", f"Coding question: `{question}`")

    response_info = {
        "coding_results": pd.DataFrame(),
        "status_code": None,
        "elapsed_time": None,
        "usage": None,
        "retries": None,
    }
    max_overload_retries = 3
    overload_retry_count = 0
    overload_backoff_seconds = 1.0
    question_answer = None
    try:
        question_answer = [
            question_answer
            for question_answer in answers.keys()
            if question_answer.split("_")[0] == question
        ][0]
    except Exception as e:
        notify("error", f"Error in format question `{question}`: {e}")
        logger.exception("Error mapping question `%s` to answer group", question)
        response_info["error"] = str(e)
        return response_info

    if answers[question_answer].empty:
        notify("warning", f"No answers to code for question: `{question}`")
        return response_info

    system_prompt = """
        You are a highly skilled NLP model that classifies open ended survey answers into categories from a provided codebook.

        INPUT FORMAT RULES
        - The input will consist of two parts: the survey data and the codebook.
        - The survey data will be provided as a dictionary where keys are in the format `question_id-Response_ID` and values are the corresponding survey answers.
        - The codebook will be provided as a dictionary where keys are code IDs and values are the corresponding code descriptions.
        - The answer might not be exactly like the description of the code in terms of misspellings, variations or letter case, but it should be classified based on the closest match in meaning, content, and semantic.

        OUTPUT FORMAT RULES
        - You MUST respond ONLY with a valid Python dictionary.
        - Do NOT output explanations, reasoning, comments, markdown, or chain-of-thought.
        - Do NOT output any text before or after the dictionary.
        - The output must be directly parseable with Python's ast.literal_eval().

        DICTIONARY STRUCTURE
        The dictionary must follow this structure:

        {
            "question_id-Response_ID": ["code1", "code2"],
            "question_id-Response_ID": ["codeX"]
        }

        NOTE: Each key corresponds to a specific survey answer, and the value is a list of integer codes (the key of the dictionary) from the codebook that best classify that answer.
        NOTE: Do NOT return code descriptions, only the code IDs as integers.
        NOTE: Do not restrict to only one code per answer. If multiple codes apply, return all relevant codes in a list.

        KEY RULES
        - Keys MUST be the exact question_id-Response_ID from the input.
        - Keys must NEVER be modified.
        - Keys must be copied EXACTLY character-by-character from the input.
        - Never translate, normalize, paraphrase, or regenerate keys.
        - Never invent new keys.
        - Never remove keys.

        CRITICAL IDENTIFIER RULES
        Identifiers such as question_id and Response_ID are immutable identifiers.

        You MUST:
        - Copy them exactly as they appear in the input
        - Preserve every character
        - Preserve capitalization
        - Preserve punctuation

        Allowed characters for identifiers are STRICTLY:
        A-Z a-z 0-9 _ . -

        Do NOT introduce any other characters.

        The following are strictly forbidden:
        - Chinese characters
        - Full-width Unicode characters
        - Accented characters
        - Any non-ASCII symbol

        If a key contains any character outside the allowed set, the output is invalid.

        CLASSIFICATION RULES
        - Each answer MUST receive at least one code.
        - Always return a list of codes.
        - Never return an empty list.
        - Never leave an answer uncoded.

        If an answer does not match any category in the codebook, classify it as the closest option to:
        "Incorrect mention".

        The codebook may be written in Spanish.

        ADDITIONAL RULES
        - Do NOT hallucinate question_id values.
        - Do NOT hallucinate Response_ID values.
        - Do NOT change the format question_id-Response_ID.
        - Do NOT reorder or alter identifiers.
        - Always return exactly the identifiers provided in the input.

        REMEMBER
        Return ONLY the Python dictionary and NOTHING else.
    """

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

    start_time = time.time()
    if LOG_LLM_IO:
        prompt_preview = user_prompt[:1000]
        logger.info(
            {
                "event": "llm_prompt",
                "question_id": question,
                "prompt_preview": prompt_preview,
                "prompt_size": len(user_prompt),
                "prompt_truncated": len(user_prompt) > len(prompt_preview),
            }
        )

    while True:
        try:
            response, transport_retries = model.send(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )
        except Exception as e:
            logger.exception("Error in request for question `%s`", question)
            response_info["error"] = str(e)
            notify("error", f"Error in request for question `{question}`: {e}")
            return response_info

        response_content_type = response.headers.get("Content-Type", "")
        response_body = response.text or ""
        response_body_preview = response_body[:500]
        is_html_response = "application/json" not in response_content_type.lower()
        is_overload_drop = "unconditional drop overload" in response_body.lower()

        if is_html_response and is_overload_drop and overload_retry_count < max_overload_retries:
            overload_retry_count += 1
            sleep_seconds = overload_backoff_seconds + random.uniform(0, 0.5)
            logger.warning(
                "Overload response for question `%s` (retry=%s/%s, status=%s, content_type=%s, sleep=%.2fs)",
                question,
                overload_retry_count,
                max_overload_retries,
                response.status_code,
                response_content_type,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
            overload_backoff_seconds *= 2
            continue

        retries = transport_retries + overload_retry_count
        break

    end_time = time.time()
    elapsed_time = end_time - start_time

    formatted_time = format_time(elapsed_time)

    response_info["status_code"] = response.status_code
    response_info["retries"] = retries
    response_info["elapsed_time"] = formatted_time

    response_body_preview = (response.text or "")[:500]
    response_content_type = response.headers.get("Content-Type", "")

    if response.status_code != 200:
        logger.error(
            "Non-200 LLM response for question `%s` (status=%s, content_type=%s, body_preview=%s)",
            question,
            response.status_code,
            response_content_type,
            response_body_preview,
        )
        notify(
            "error",
            f"Model response unsuccessfull for question: `{question}` with status code {response.status_code}. Body preview: {response_body_preview}"
        )
        response_info["usage"] = None
        response_info["error"] = (
            f"Non-200 response: {response.status_code}. "
            f"content_type={response_content_type}"
        )
        response_info["coding_results_raw"] = response_body_preview
        return response_info

    if "application/json" not in response_content_type.lower():
        logger.error(
            "Unexpected content type for question `%s` (content_type=%s, body_preview=%s)",
            question,
            response_content_type,
            response_body_preview,
        )
        notify(
            "error",
            f"Unexpected content type for question `{question}`: {response_content_type}"
        )
        response_info["usage"] = None
        response_info["error"] = f"Unexpected content type: {response_content_type}"
        response_info["coding_results_raw"] = response_body_preview
        return response_info

    try:
        response_json = response.json()
    except Exception as e:
        logger.exception(
            "Error decoding JSON response for question `%s` (status=%s, content_type=%s, body_preview=%s)",
            question,
            response.status_code,
            response_content_type,
            response_body_preview,
        )
        notify(
            "error",
            f"Error decoding model response for question `{question}`: {e}"
        )
        response_info["usage"] = None
        response_info["error"] = str(e)
        response_info["coding_results_raw"] = response_body_preview
        return response_info

    response_info["usage"] = response_json.get("usage")

    try:
        response_content = response_json["choices"][0]["message"]["content"]
    except Exception as e:
        logger.exception(
            "Unexpected JSON schema for question `%s` (response_json=%s)",
            question,
            str(response_json)[:500],
        )
        notify(
            "error",
            f"Unexpected model response schema for question `{question}`: {e}"
        )
        response_info["error"] = f"Unexpected response schema: {e}"
        response_info["coding_results_raw"] = str(response_json)[:1000]
        return response_info

    response_content_cleaned = remove_chain_of_thought(response_content)

    coding_dict = (
        response_content_cleaned.replace("json", "")
        .replace("\\n", "")
        .replace("\n", "")
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
        notify(
            "error",
            f"Error parsing Llama response to JSON for question `{question}`: {e}"
        )
        logger.error(
            "Error parsing coding dict for question `%s` (content_preview=%s)",
            question,
            coding_dict[:500],
        )
        return response_info

    expected_keys = set(answers[question_answer]["question_id-Response_ID"].tolist())
    returned_keys = set(coding_result.keys())
    matched_keys = expected_keys.intersection(returned_keys)
    unexpected_keys = returned_keys.difference(expected_keys)
    missing_keys = expected_keys.difference(returned_keys)

    if not matched_keys:
        response_info["error"] = "No valid identifiers matched expected survey keys"
        response_info["coding_results_raw"] = str(coding_result)[:1000]
        logger.error(
            "No matching keys for question `%s` (expected_count=%s, returned_count=%s, returned_preview=%s)",
            question,
            len(expected_keys),
            len(returned_keys),
            str(list(returned_keys)[:10]),
        )
        return response_info

    if unexpected_keys or missing_keys:
        logger.warning(
            "Partial key match for question `%s` (matched=%s, missing=%s, unexpected=%s)",
            question,
            len(matched_keys),
            len(missing_keys),
            len(unexpected_keys),
        )
        response_info["warning"] = (
            f"Partial key match: matched={len(matched_keys)}, "
            f"missing={len(missing_keys)}, unexpected={len(unexpected_keys)}"
        )

    coding_result = {key: coding_result[key] for key in matched_keys}

    if LOG_LLM_IO:
        response_preview = str(coding_result)[:1000]
        logger.info(
            {
                "event": "llm_response",
                "question_id": question,
                "response_preview": response_preview,
                "response_size": len(str(coding_result)),
                "response_truncated": len(str(coding_result)) > len(response_preview),
            }
        )

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

    notify("success", f"Model response successfull for question: `{question}`")


def preprocessing(temp_file_name_xlsx: str, temp_file_name_sav: str):
    code_books = pd.read_excel(temp_file_name_xlsx, sheet_name=None)
    questions = list(code_books.keys())

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
    max_parallel_questions = max(
        1, int(os.getenv("PREPROCESSING_MAX_PARALLEL_QUESTIONS", "4"))
    )
    question_semaphore = Semaphore(max_parallel_questions)

    results = {}

    threads = []
    completion_queue: Queue = Queue()
    status_containers = {}
    for question in questions:
        status_containers[question] = st.empty()
        status_containers[question].info(f"Coding question: `{question}`")

        def run_question(question: str):
            with question_semaphore:
                response_info = process_question(
                    question,
                    prompt_template,
                    answers,
                    code_books,
                    model,
                    None,
                    results,
                )
                if isinstance(response_info, dict):
                    results[question] = response_info
                completion_queue.put(question)

        t = Thread(
            target=run_question,
            args=(question,),
        )
        add_script_run_ctx(t)  # Necessary for Streamlit to track the thread context
        threads.append(t)
        try:
            t.start()
            # time.sleep(0.5)
        except Exception as e:
            st.error(f"Question {question} generated an exception: {e}")
            raise ValueError(f"Question {question} generated an exception: {e}")
    completed_questions = set()
    total_questions = len(questions)

    while len(completed_questions) < total_questions:
        try:
            question = completion_queue.get(timeout=0.2)
        except Empty:
            continue

        if question in completed_questions:
            continue

        completed_questions.add(question)

        response_info = results.get(question, {})
        error = response_info.get("error") if isinstance(response_info, dict) else None
        warning = response_info.get("warning") if isinstance(response_info, dict) else None
        coding_results_df = (
            response_info.get("coding_results")
            if isinstance(response_info, dict)
            else pd.DataFrame()
        )
        if error:
            status_containers[question].error(
                f"Question `{question}` finished with error: {error}"
            )
        elif isinstance(coding_results_df, pd.DataFrame) and coding_results_df.empty:
            status_containers[question].warning(
                f"Question `{question}` produced no coding rows"
            )
        elif warning:
            status_containers[question].warning(
                f"Question `{question}` coded with warning: {warning}"
            )
        else:
            status_containers[question].success(
                f"Question `{question}` coded successfully"
            )

    for t in threads:
        t.join()

    return results
