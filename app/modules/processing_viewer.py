from typing import Literal, Callable
import traceback
import ast
import re

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

import numpy as np
import pandas as pd

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.cloud import CloudStorageClient
from app.modules.processing import (
    significant_differences,
)
from app.modules.utils import (
    get_countries,
    get_temp_file,
    column_letters,
    roman,
    _to_show,
    _to_code,
)

cs_client = CloudStorageClient("connecta-app-1-service-processing")

db = firestore.client()

# CSS to highlight headers and index of the dataframe
table_styles = [
    {"selector": "tr:nth-child(even)", "props": [("background-color", "#1f1f1f")]},
    {"selector": "tr:nth-child(odd)", "props": [("background-color", "#030303")]},
    {"selector": "tr:hover", "props": [("background-color", "#666666")]},
]

stats_template = {
    "Mean": None,
    "Standard Deviation": None,
    "Standard Error": None,
    "Total": None,
    "Total Answers": None,
    "%": None,
}


@st.cache_data(show_spinner=False)
def get_business_data():
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()

    if document.exists:
        business_data = document.to_dict()
        return business_data


def get_category_id(category_name: str | None) -> str | None:
    if not category_name:
        return None

    category_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("categories")
        .where(filter=FieldFilter("name", "==", category_name))
        .limit(1)
        .stream()
    )
    for category_doc in category_query:
        return category_doc.id
    print(f"No category found with name: {category_name}")
    return None


@st.cache_data(show_spinner=False)
def get_subcategory_id(
    subcategory_name: str | None, category_id: str | None
) -> str | None:
    if not subcategory_name or not category_id:
        return None

    subcategory_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("subcategories")
        .where(filter=FieldFilter("name", "==", subcategory_name))
        .where(filter=FieldFilter("category_id", "==", category_id))
        .limit(1)
        .stream()
    )
    for subcategory_doc in subcategory_query:
        return subcategory_doc.id
    print(f"No subcategory found with name: {subcategory_name}")
    return None


@st.cache_data(show_spinner=False)
def get_question_type(question_type_id: int) -> dict[str, str] | None:
    question_type_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("question_types")
        .document(question_type_id)
        .get()
    )
    if question_type_query.exists:
        return question_type_query.to_dict()
    return None


@st.cache_data(show_spinner=False)
def get_group_ids(
    group_name: list[str] | None, category_id: str | None, subcategory_id: str | None
) -> list[str] | None:
    if not group_name or not subcategory_id:
        return None

    group_ids = []
    for name in group_name:
        group_query = (
            db.collection("settings")
            .document("survey_config")
            .collection("groups")
            .where(filter=FieldFilter("name", "==", name))
            .where(filter=FieldFilter("category_id", "==", category_id))
            .where(filter=FieldFilter("subcategory_id", "==", subcategory_id))
            .limit(1)
            .stream()
        )
        for group_doc in group_query:
            group_ids.append(group_doc.id)
            break
        else:
            print(f"No group found with name: {name}")

    return group_ids if group_ids else None


@st.cache_data(show_spinner=False)
def get_questions(
    category_name: str | None = None,
    subcategory_name: str | None = None,
    groups_names: list[str] | None = None,
) -> dict[str, list[str]]:
    category_id = get_category_id(category_name)
    subcategory_id = get_subcategory_id(subcategory_name, category_id)

    questions_ref = (
        db.collection("settings").document("survey_config").collection("questions")
    )
    if category_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("category_id", "==", category_id)
        )
    if subcategory_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("subcategory_id", "==", subcategory_id)
        )

    # If no groups are selected, get all groups for this category/subcategory
    if not groups_names:
        groups_ref = (
            db.collection("settings").document("survey_config").collection("groups")
        )
        if category_id:
            groups_ref = groups_ref.where(
                filter=FieldFilter("category_id", "==", category_id)
            )
        if subcategory_id:
            groups_ref = groups_ref.where(
                filter=FieldFilter("subcategory_id", "==", subcategory_id)
            )
        group_docs = groups_ref.stream()
        group_ids = [doc.id for doc in group_docs]
    else:
        group_ids = get_group_ids(groups_names, category_id, subcategory_id)

    if group_ids:
        questions_ref = questions_ref.where(
            filter=FieldFilter("group_id", "in", group_ids)
        )

    questions_query = questions_ref.stream()
    questions = [question_doc.to_dict() for question_doc in questions_query]

    # Get all groups to maintain consistent ordering
    all_groups_ref = (
        db.collection("settings").document("survey_config").collection("groups")
    )
    if category_id:
        all_groups_ref = all_groups_ref.where(
            filter=FieldFilter("category_id", "==", category_id)
        )
    if subcategory_id:
        all_groups_ref = all_groups_ref.where(
            filter=FieldFilter("subcategory_id", "==", subcategory_id)
        )

    all_groups = {doc.id: doc.to_dict() for doc in all_groups_ref.stream()}
    all_groups = dict(sorted(all_groups.items(), key=lambda item: item[1]["order"]))
    # Create a mapping of group_id to its index in the sorted groups
    group_order = {group_id: idx for idx, group_id in enumerate(all_groups.keys())}
    # Sort questions by group order first, then by question order
    sorted_questions = sorted(
        questions,
        key=lambda q: (
            group_order.get(q.get("group_id", ""), float("inf")),  # Sort by group order
            q.get("order", float("inf")),  # Then by question order
        ),
    )

    # Group questions by their group name
    grouped_questions = {}
    for question in sorted_questions:
        group_id = question.get("group_id", "")
        groups_name = all_groups.get(group_id, "Unknown")["name"]
        if groups_name not in grouped_questions:
            grouped_questions[groups_name] = []
        grouped_questions[groups_name].append(
            question
            # question.get("label", "")
            # {"label": question.get("label", ""), "code": question.get("code", "")}
        )

    return grouped_questions


def get_config_key_cross_questions(for_: Literal["filters", "grids"]):
    match for_:
        case "filters":
            return "cross_variables"
        case "grids":
            return "section_variables"


def get_cross_questions(
    config: dict, for_: Literal["filters", "grids"] | None = None
) -> list[str]:
    key = get_config_key_cross_questions(for_)
    return [question["label"] for question in config[key]]


def get_cross_questions_codes(
    cross_questions: list[str],
    config: dict,
    parsed_questions_dict: dict,
    for_: Literal["filters", "grids"] | None = None,
) -> list[str]:
    # Create a dictionary mapping labels to codes for efficient lookup
    key = get_config_key_cross_questions(for_)
    label_to_code = {item["label"]: item["variable"] for item in config[key]}

    # Get codes for each target label
    return [
        find_codes_list_by_code(label_to_code[label], parsed_questions_dict)
        for label in cross_questions
        if label in label_to_code
    ]


@st.cache_data(show_spinner=False)
def get_categories() -> list[str]:
    db = firestore.client()
    root_doc = db.collection("settings").document("survey_config")

    # Query all documents in the categories collection
    categories_query = root_doc.collection("categories").stream()

    # Collect and return the category names
    category_names = [
        category_doc.to_dict().get("name") for category_doc in categories_query
    ]
    return category_names


@st.cache_data(show_spinner=False)
def get_subcategories(category: str) -> list[str]:
    # Get the category ID
    category_id = get_category_id(category)
    if not category_id:
        return []

    root_doc = db.collection("settings").document("survey_config")
    # Reference to the subcategories collection
    subcategories_ref = root_doc.collection("subcategories")

    # Query for subcategories with the given category ID
    subcategories_query = subcategories_ref.where(
        filter=FieldFilter("category_id", "==", category_id)
    ).stream()

    # Collect and return the subcategory names
    subcategory_names = [
        subcategory_doc.to_dict().get("name") for subcategory_doc in subcategories_query
    ]
    return subcategory_names


@st.cache_data(show_spinner=False)
def get_question_groups(category: str, subcategory: str) -> list[str]:
    # Get the category ID
    category_id = get_category_id(category)
    if not category_id:
        return []

    # Get the subcategory ID
    subcategory_id = get_subcategory_id(subcategory, category_id)
    if not subcategory_id:
        return []

    root_doc = db.collection("settings").document("survey_config")
    # Reference to the groups collection
    groups_ref = root_doc.collection("groups")

    # Query for groups with the given category and subcategory IDs
    groups_query = (
        groups_ref.where(filter=FieldFilter("category_id", "==", category_id))
        .where(filter=FieldFilter("subcategory_id", "==", subcategory_id))
        .stream()
    )
    groups = [group_query.to_dict() for group_query in groups_query]
    ordered_groups = sorted(groups, key=lambda x: x.get("order"))
    group_names = [group_doc.get("name") for group_doc in ordered_groups]
    return group_names


def get_studies_names(
    category: str, subcategory: str, country_code: str, company: str
) -> list[str]:
    """Get studies names from files in storage bucket and transform them
    to show them in the UI."""
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    study_names = cs_client.list_files(
        f"databases/{category}/{subcategory}/{country_code}/{company}"
    )
    return list(
        set([_to_show(study_name.split(".")[0], "title") for study_name in study_names])
    )


def get_study_countries(
    category: str,
    subcategory: str,
) -> list[str]:
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    countries_iso_2_code = get_countries()
    iso_countries = {iso: country for country, iso in countries_iso_2_code.items()}
    files = cs_client.list_files(f"databases/{category}/{subcategory}")
    study_countries = list(set([file.split("/")[0] for file in files]))
    return [_to_show(iso_countries[country_code]) for country_code in study_countries]


@st.cache_data(show_spinner=False)
def get_available_countries(studies_id: str) -> list[str]:
    studies_names = get_studies_names()
    countries_iso = get_countries()
    iso_countries = {iso: country for country, iso in countries_iso.items()}
    return [
        iso_countries[study_name.split("_")[1].upper()]
        for study_name in studies_names
        if study_name.split("_")[0] == studies_id
    ]


@st.cache_data(show_spinner=True)
def download_studies_data(
    category: str, subcategory: str, country_code: str, company: str, studies: list[str]
) -> dict[str, dict[str, str]]:
    """Download the respective files (.sav, .json) from storage bucket for the
    selected studies."""
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    blob_path = f"databases/{category}/{subcategory}/{country_code}/{company}"

    studies_files = {}

    for study in studies:
        studies_files[study] = {}
        for file in ("sav", "json"):
            blob_name = f"{blob_path}/{_to_code(study)}.{file}"
            file_bytes = cs_client.download_as_bytes(blob_name)
            studies_files[study][file] = get_temp_file(file_bytes, f".{file}")

    return studies_files


def df_to_html(df: pd.DataFrame) -> str:
    # CSS to highlight headers and index of the dataframe
    table_styles = [
        dict(selector="th", props="font-size: 0.8em; "),
        dict(selector="td", props="font-size: 0.8em; text-align: right"),
        dict(selector="tr:hover", props="background-color: lightgray"),
    ]

    return (
        df
        # Make pandas.Styler from the DataFrame
        .style
        # Negative numbers in red
        # .apply(lambda cell: np.where(cell != 0, "color: red", None), axis=1)
        # Format numbers to 2 decimal places, leave strings as is
        .format(
            lambda x: (
                f"{x:.2f}"
                if isinstance(x, (float, int)) and x % 1 != 0
                else f"{int(x)}"
                if isinstance(x, (float, int))
                else x
            )
        )
        # Apply CSS
        .set_table_styles(table_styles)
        # Convert DataFrame Styler object to formatted HTML text
        .to_html(escape=False, border=5),
    )


def filter_df(
    fields: DeltaGenerator, filters: dict, metadata_df: pd.DataFrame, db: pd.DataFrame
) -> pd.DataFrame:
    for field, filter in zip(fields, filters):
        filter_name = filter["label"]
        filter_variable = filter["variable"]
        if filter_variable == "F2":
            if db["F2"].isna().all():
                continue
            disabled = len(db["F2"].dropna().unique()) == 0
            selection = field.slider(
                filter_name,
                value=(
                    int(min(db["F2"].dropna().unique())) if not disabled else 0,
                    int(max(db["F2"].dropna().unique())) if not disabled else 0,
                ),
                disabled=disabled,
            )
            db = db[
                (db["F2"] >= selection[0]) & (db["F2"] <= selection[1])
            ].reset_index(drop=True)
        else:
            options_str = metadata_df[metadata_df.index == filter_variable].loc[
                filter_variable, "values"
            ]
            if options_str:
                try:
                    options = eval(options_str)
                    mirrored_options = {v: k for k, v in options.items()}
                except Exception:
                    options = []

            selection = field.multiselect(filter_name, sorted(options.values()))
            selection = [mirrored_options[option] for option in selection]

            if selection:
                db = db[db[filter_variable].isin(selection)].reset_index(drop=True)

    return db


def get_question_codes(
    selected_questions: list[str],
    questions_by_group: dict[str, list[str]],
):
    selected_questions_labels = [q.split(" | ")[1] for q in selected_questions]

    question_codes = []
    for _, questions in questions_by_group.items():
        for question in questions:
            if question["label"] in selected_questions_labels:
                question_codes.append(question["code"])

    return question_codes


def transform_variable(
    question_code: str,
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.Series:
    mapping: dict = eval(metadata_df.loc[question_code]["values"])
    if len(mapping) == 1 and not next(iter(mapping.values())):
        return (
            db[db.columns[db.columns.str.contains(question_code)][0]]
            .astype(int)
            .fillna(0)
        )
    else:
        return (
            db[db.columns[db.columns.str.contains(question_code)][0]]
            .map(mapping)
            .fillna(0)
            .astype(str)
            .str.strip()
        )


def transform_cross_variable(
    cross_question_code: str,
    cross_question_label: str,
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.Series:
    mapping: dict = eval(metadata_df.loc[cross_question_code]["values"])
    return db[cross_question_code].map(mapping).rename(cross_question_label).fillna(0)


def reorder_contingency_table(
    question_code: str,
    cross_question_code: str,
    df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    selected_question: str,
) -> pd.DataFrame:
    group = selected_question.split(" | ")[0]
    column_mapping: dict = eval(metadata_df.loc[cross_question_code]["values"])
    new_columns = [
        column_name.strip()
        for column_name in column_mapping.values()
        if column_name in df.columns
    ]
    if "All" in df.columns:
        new_columns = ["All"] + new_columns

    reordered_df = df[new_columns]

    index_mapping: dict = eval(metadata_df.loc[question_code]["values"])
    index_mapping = {key: value.strip() for key, value in index_mapping.items()}

    if len(index_mapping) == 1 and not next(iter(index_mapping.values())):
        reordered_df = (
            reordered_df.drop(index="All")
            if "All" in reordered_df.index
            else reordered_df
        )
        return reordered_df.dropna(how="all")

    reordered_df = reordered_df.reindex(index_mapping.values())

    return reordered_df.dropna(how="all") if group == "FILTERS" else reordered_df


def parse_question_codes(columns: pd.Index, metadata_df: pd.DataFrame):
    """
    Parse column names and create a hierarchical dictionary of question codes,
    associating each top-level group with its label from metadata_df.

    Args:
        columns (pandas.Index): List of column names from the dataframe.
        metadata_df (pd.DataFrame): DataFrame containing metadata with column names as index and 'label' column.

    Returns:
        dict: Dictionary with principal codes as keys, each containing its label and grouped child codes.
    """
    # Convert pandas Index to list if necessary
    columns_list = columns.tolist() if hasattr(columns, "tolist") else list(columns)

    temp_question_dict = {}
    skip_f_codes = False

    for col in columns_list:
        # Handle special markers
        if col == "ABIERTAS":
            skip_f_codes = True
            continue
        elif col == "ETIQUETAS":
            break

        # Skip non-question columns
        if col in ["N.enc.3", "tipo.3", "N.encuesta.4", "tipo_super.4"]:
            continue

        # Handle F-type questions (e.g., F11A1, F11A2, F8R1, F8R2)
        if col.startswith("F"):
            # Skip F codes between ABIERTAS and ETIQUETAS
            if skip_f_codes:
                continue

            # Extract base code for F-type questions
            if "A" in col:
                base_code = col.split("A")[
                    0
                ]  # Get the base code (e.g., F11 from F11A1)
            elif "R" in col:
                base_code = col.split("R")[0]  # Get the base code (e.g., F8 from F8R1)
            else:
                base_code = col.split("_")[0]  # Get the base code (e.g., F1 from F1)

            if base_code not in temp_question_dict:
                temp_question_dict[base_code] = []
            temp_question_dict[base_code].append(col)

        # Handle any questions with visit information (e.g., P26_V1_R1, MARCA_V4_R1, CUSTOM_V2_ABC)
        elif "_V" in col:
            base_code = col.split("_")[
                0
            ]  # Get the base code (e.g., P26, PRECIO, MARCA, CUSTOM)

            # Extract visit information
            visit = col.split("_")[
                1
            ]  # Get the visit (e.g., V4 from P5_V4_R1A3 or S1_V4_R1)

            if base_code not in temp_question_dict:
                temp_question_dict[base_code] = {}

            if visit not in temp_question_dict[base_code]:
                temp_question_dict[base_code][visit] = []

            temp_question_dict[base_code][visit].append(col)

        elif "BACKUP" in col:
            temp_question_dict[col] = [col]

        # Handle other question types
        else:
            base_code = col.split("_")[0]  # Get the base code
            if base_code not in temp_question_dict:
                temp_question_dict[base_code] = []
            temp_question_dict[base_code].append(col)

    # Sort the lists to maintain original order
    for key in temp_question_dict:
        if isinstance(
            temp_question_dict[key], dict
        ):  # For P-type and S-type questions with visits
            for visit in temp_question_dict[key]:
                temp_question_dict[key][visit].sort(key=lambda x: columns_list.index(x))
        else:  # For other question types
            temp_question_dict[key].sort(key=lambda x: columns_list.index(x))

    return associate_labels_with_codes(temp_question_dict, metadata_df)


def associate_labels_with_codes(
    grouped_codes_dict: dict, metadata_df: pd.DataFrame
) -> dict:
    """
    Associates labels from metadata_df with the first inner code of each top-level group.

    Args:
        grouped_codes_dict (dict): The dictionary of grouped question codes (from parse_question_codes).
        metadata_df (pd.DataFrame): DataFrame containing metadata with column names as index and 'label' column.

    Returns:
        dict: Dictionary with principal codes as keys, each containing its label and grouped child codes.
    """
    final_grouped_dict = {}
    for base_code, value in grouped_codes_dict.items():
        first_inner_code = None
        if isinstance(value, dict):  # Nested dictionary for visits
            # Get the first visit key (e.g., 'V1')
            first_visit_key = list(value.keys())[0]
            # Get the first code in that visit (e.g., 'P26_V1_R1')
            first_inner_code = value[first_visit_key][0]
        else:  # Simple list
            first_inner_code = value[0]

        label = None
        if first_inner_code in metadata_df.index:
            label = metadata_df.loc[first_inner_code]["label"]

        final_grouped_dict[base_code] = {"label": label, "codes": value}
    return final_grouped_dict


def get_codes_by_labels(
    labels: list[str], parsed_questions_dict: dict
) -> dict[str, list[str]]:
    """
    Retrieves a list of codes for a given list of labels, maintaining the original order.

    Args:
        labels (list[str]): A list of labels to retrieve codes for.
        parsed_questions_dict (dict): The dictionary output from parse_question_codes.

    Returns:
        list[list[str]]: A list of lists, where each inner list contains the codes
                          corresponding to an input label, in the same order.
    """
    result_codes = {}
    for label_to_find in labels:
        found_codes_for_label = []
        for base_code, data in parsed_questions_dict.items():
            if data["label"] == label_to_find:
                codes = data["codes"]
                if isinstance(codes, dict):  # Handle nested dictionary for visits
                    for visit_key in codes:
                        found_codes_for_label.extend(codes[visit_key])
                else:  # Handle simple list of codes
                    found_codes_for_label.extend(codes)
                # Assuming labels are unique per base_code, break after finding
                break
        result_codes[label_to_find] = found_codes_for_label
    return result_codes


def find_codes_list_by_code(
    target_code: str, parsed_questions_dict: dict
) -> list[str] | None:
    """
    Searches for a specific code within the 'codes' list of the parsed questions dictionary
    and retrieves the entire list the code is part of.

    Args:
        target_code (str): The code to search for.
        parsed_questions_dict (dict): The dictionary output from parse_question_codes.

    Returns:
        list[str] | None: The list of codes that the target_code belongs to, or None if not found.
    """
    for base_code, data in parsed_questions_dict.items():
        codes = data.get("codes", [])
        if isinstance(codes, dict):  # Handle nested dictionary for visits
            for visit_key in codes:
                if target_code in codes[visit_key]:
                    return codes[visit_key]
        else:  # Handle simple list of codes
            if target_code in codes:
                return codes
    return None


def get_filter_questions(metadata_df: pd.DataFrame) -> list[str]:
    filtered_labels = []
    for idx in metadata_df.index:
        label = metadata_df.loc[idx]["label"]
        values_str = metadata_df.loc[idx]["values"]

        is_candidate = False
        if values_str:
            try:
                evaluated_values = ast.literal_eval(values_str)
                if isinstance(evaluated_values, dict):
                    is_candidate = True
            except (ValueError, SyntaxError):
                # Handle cases where values_str is not a valid Python literal
                pass

        if is_candidate:
            filtered_labels.append(label)

    all_labels_in_index_order = filtered_labels

    ref_index = -1
    for i, label in enumerate(all_labels_in_index_order):
        if label.startswith("REF"):
            ref_index = i
            break  # Found the first one, so break

    if ref_index != -1:
        # Return elements from the beginning up to (but not including) the first label starting with 'REF'
        return list(dict.fromkeys(all_labels_in_index_order[:ref_index]))
    else:
        # No label starting with 'REF' found, return all labels
        return list(dict.fromkeys(all_labels_in_index_order))


def get_related_question_codes(
    selected_questions_codes: list[str], parsed_questions: dict
) -> dict[str, list[str]]:
    result = {}
    for parent_code in selected_questions_codes:
        if parent_code in parsed_questions:
            question_info = parsed_questions[parent_code]
            label = question_info["label"]
            codes = question_info["codes"]

            if isinstance(codes, dict):  # Handle nested dictionary for visits
                all_codes = []
                for visit, visit_codes in codes.items():
                    all_codes.extend(visit_codes)
                result[label] = all_codes
            else:  # Handle simple list of codes
                result[label] = codes

    return result


def concat_update(base_df: pd.DataFrame, appended_df: pd.DataFrame) -> pd.DataFrame:
    """
    Concatenate values from df1 and df2 at each cell (as strings), similar to update but concatenating.
    """

    def concat(x, y):
        if x == "":
            x = np.nan
        if y == "":
            y = np.nan
        if pd.isna(x) and pd.isna(y):
            return np.nan
        return " ".join([str(val) for val in [x, y] if pd.notna(val)])

    # Apply combine on each column
    result = base_df.copy()

    for col in result.columns.intersection(appended_df.columns):
        result[col] = result[col].combine(appended_df[col], concat)

    return result


def build_cross_contingency_table(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    cross_questions_codes: list[str],
    cross_variables: list[str],
    question_code: str,
    selected_question: str,
    view_type: Literal["Grouped", "Detailed"] = "Detailed",
    questions_by_group: dict[str, list[str]] | None = None,
) -> list[pd.DataFrame]:
    contingency_tables_count = []

    for i, (cross_question_code, cross_question_label) in enumerate(
        zip(cross_questions_codes, cross_variables)
    ):
        transformed_variable = transform_variable(question_code, db, metadata_df)
        sub_contingency_tables_count = []
        for j, sub_cross_question_code in enumerate(cross_question_code):
            transformed_cross_variable = transform_cross_variable(
                sub_cross_question_code, cross_question_label, db, metadata_df
            )

            contingency_table_count = pd.crosstab(
                transformed_variable,
                transformed_cross_variable,
                margins=True if i == 0 and j == 0 else False,
            )

            contingency_table_count = reorder_contingency_table(
                question_code,
                sub_cross_question_code,
                contingency_table_count,
                metadata_df,
                selected_question,
            )

            if view_type == "Grouped":
                contingency_table_count = create_grouped_df(
                    contingency_table_count,
                    questions_by_group,
                    selected_question,
                    db,
                    metadata_df,
                    question_code,
                    sub_cross_question_code,
                )
            else:
                contingency_table_count = create_detailed_df(
                    selected_question,
                    db,
                    metadata_df,
                    question_code,
                    sub_cross_question_code,
                    contingency_table_count,
                    questions_by_group,
                )

            sub_contingency_tables_count.append(contingency_table_count)

        contingency_table_count = pd.concat(sub_contingency_tables_count, axis=1)

        index_mapping: dict = eval(metadata_df.loc[question_code]["values"])
        index_mapping = {key: value.strip() for key, value in index_mapping.items()}

        new_column_tuples = []

        for j, col_name in enumerate(contingency_table_count.columns):
            if col_name == "All":
                new_column_tuples.append(("TOTAL", "TOTAL"))
            else:
                new_column_tuples.append((cross_question_label, col_name))

        contingency_table_count.columns = pd.MultiIndex.from_tuples(new_column_tuples)

        contingency_tables_count.append(contingency_table_count)

    return contingency_tables_count


def create_scale_question_df(question_table: pd.DataFrame) -> pd.DataFrame:
    # Collapse the "Options" level
    options_level = -1

    options_values = (
        question_table.index.get_level_values(options_level).astype(str).str.strip()
    )

    # T2B: sum all options starting with "4." or "5."
    t2b_mask = options_values.str.startswith("4.") | options_values.str.startswith("5.")
    t2b_df = question_table[t2b_mask].copy()
    t2b_df["Options"] = "T2B"
    t2b_df = t2b_df.set_index("Options", append=True)
    t2b_df = t2b_df.groupby(level=options_level).sum(numeric_only=True)

    # TB: only options starting with "5."
    tb_mask = options_values.str.startswith("5.")
    tb_df = question_table[tb_mask].copy()
    tb_df["Options"] = "TB"
    # Rename all matching to "TB"
    tb_df = tb_df.set_index("Options", append=True)
    tb_df = tb_df.groupby(level=options_level).sum(numeric_only=True)

    # Concatenate
    return pd.concat([t2b_df, tb_df])


def create_jr_question_df(question_table: pd.DataFrame) -> pd.DataFrame:
    old_label = question_table.index[2]
    question_table = question_table.rename(index={old_label: "JR"})
    question_table.iloc[0] = question_table.iloc[0] + question_table.iloc[1]
    question_table.iloc[4] = question_table.iloc[3] + question_table.iloc[4]
    question_table = question_table.drop(question_table.index[[1, 3]])
    return question_table


def create_grouped_df(
    question_table: pd.DataFrame,
    questions_by_group: dict,
    selected_question: str,
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    question_code: str,
    sub_cross_question_code: str,
) -> pd.DataFrame:
    group, label = selected_question.split(" | ")
    group_questions = questions_by_group[group]

    question_config = list(filter(lambda d: d.get("label") == label, group_questions))

    if question_config:
        question_config = question_config[0]
        question_type_config = get_question_type(question_config["question_type_id"])

        match question_type_config["code"]:
            case "E":
                collapsed_table = create_scale_question_df(question_table)
            case "N":
                collapsed_table = question_table
            case "J":
                collapsed_table = create_jr_question_df(question_table)
            case "U":
                collapsed_table = question_table
            case "M":
                collapsed_table = question_table
            case "A":
                collapsed_table = question_table
            case _:
                collapsed_table = question_table

        collapsed_table = append_summary_rows(
            db,
            metadata_df,
            question_code,
            sub_cross_question_code,
            collapsed_table,
            question_type_config,
        )

    return collapsed_table


def append_summary_rows(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    question_code: str,
    sub_cross_question_code: str,
    df: pd.DataFrame,
    question_type_config: dict[str, str],
) -> pd.DataFrame:
    # Only operate on numeric columns for calculations
    numeric_df = df.select_dtypes(include=[np.number])
    value_mapping = eval(metadata_df.loc[sub_cross_question_code, "values"])
    value_mapping = {int(k): v for k, v in value_mapping.items()}

    # Prepare row labels (adapt for index type)
    stats_labels = question_type_config["properties"]

    stats_df = pd.DataFrame(
        index=stats_labels,
        columns=df.columns,
    )

    for value in numeric_df.columns:
        if value == "All":
            filtered_db = db.copy()
        else:
            value_code = [
                code for code, label in value_mapping.items() if label == value
            ][0]
            filtered_db = db[db[sub_cross_question_code] == value_code].reset_index(
                drop=True
            )

        question_responses = (
            filtered_db[question_code]
            .fillna("0")
            .astype(str)
            .str.strip()
            .astype(float)
            .astype(int)
        )

        stats_values = stats_template.copy()
        stats_values.update(
            {
                "Mean": question_responses.mean(),
                "Standard Deviation": question_responses.std(),
                "Standard Error": question_responses.std()
                / np.sqrt(question_responses.count()),
                "Total": question_responses.count(),
                "Total Answers": question_responses.count(),
                "%": (question_responses.count() / question_responses.count()) * 100,
            }
        )

        for stat_label in stats_labels:
            stats_df.loc[stat_label, value] = stats_values[stat_label]

    combined_df = pd.concat([df, stats_df])

    return combined_df


def sort_question_table(
    question_table: pd.DataFrame, question_config: dict, question_type_config: dict
) -> pd.DataFrame:
    stats_labels: list = question_type_config["properties"]

    # Create boolean masks for filtering
    is_stats = question_table.index.get_level_values(-1).isin(stats_labels)
    is_not_stats = ~is_stats

    # Get the index values for each group
    stats_indices = question_table.index[is_stats]
    options_indices = question_table.index[is_not_stats]

    # Select the rows for each group
    question_table_stats = question_table.loc[question_table.index.isin(stats_indices)]

    reordered_rows = []

    for first_level_value in question_table_stats.index.get_level_values(0).unique():
        for label in stats_labels:
            idx = (first_level_value, label)
            if idx in question_table_stats.index:
                reordered_rows.append(idx)

    question_table_stats = question_table_stats.loc[reordered_rows]

    question_table_options = question_table.loc[
        question_table.index.isin(options_indices)
    ]

    match question_config["sorted_by"]:
        case "options":
            match question_config["sort_order"]:
                case "desc":
                    reordered_question_table_options = (
                        question_table_options.sort_index(level=-1, ascending=False)
                    )
                case "asc":
                    reordered_question_table_options = (
                        question_table_options.sort_index(level=-1, ascending=True)
                    )
                case "original":
                    reordered_question_table_options = question_table_options
                case _:
                    reordered_question_table_options = question_table_options
        case "values":
            match question_config["sort_order"]:
                case "desc":
                    reordered_question_table_options = (
                        question_table_options.sort_values(
                            by=[("V1", "TOTAL", "TOTAL")], ascending=False
                        )
                    )
                case "asc":
                    reordered_question_table_options = (
                        question_table_options.sort_values(
                            by=[("V1", "TOTAL", "TOTAL")], ascending=True
                        )
                    )
                case "original":
                    reordered_question_table_options = question_table_options
                case _:
                    reordered_question_table_options = question_table_options

    return pd.concat([reordered_question_table_options, question_table_stats])


def create_detailed_df(
    selected_question: str,
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    question_code: str,
    sub_cross_question_code: str,
    question_table: pd.DataFrame,
    questions_by_group: dict[str, list[str]],
) -> pd.DataFrame:
    group, label = selected_question.split(" | ")
    group_questions = questions_by_group[group]

    question_config = list(filter(lambda d: d.get("label") == label, group_questions))

    if question_config:
        question_config = question_config[0]
        question_type_config = get_question_type(question_config["question_type_id"])

        # question_table = sort_question_table(question_table, question_config)
        question_table = append_summary_rows(
            db,
            metadata_df,
            question_code,
            sub_cross_question_code,
            question_table,
            question_type_config,
        )

    return question_table


def reorder_header_levels(df: pd.DataFrame, levels_order: list[int]):
    df = df.copy()
    # Move visit to last level
    df.columns = df.columns.reorder_levels(levels_order)

    # Extract original order of first two levels from the reordered columns
    first_two_levels = [col[:2] for col in df.columns]
    seen = set()
    ordered_pairs = []
    for pair in first_two_levels:
        if pair not in seen:
            ordered_pairs.append(pair)
            seen.add(pair)

    # Build new column order
    new_column_order = []
    for pair in ordered_pairs:
        visits = [col for col in df.columns if col[:2] == pair]
        new_column_order.extend(visits)
    df = df.loc[:, new_column_order]

    return df


def get_percentage_df(df: pd.DataFrame):
    df = df.copy()
    is_stat = df.index.get_level_values(-1).isin(stats_template.keys())
    non_stat_rows = ~is_stat

    # Get the "Total" row for each column
    total_answers = df.xs("Total", level=-1)

    # Ensure non-stat rows are float before division
    df.loc[non_stat_rows, :] = df.loc[non_stat_rows, :].astype(float)

    # Divide all non-stat rows at once
    df.loc[non_stat_rows, :] = (df.loc[non_stat_rows, :] / total_answers) * 100

    # Round and fill NaNs with 0 for display
    df.loc[non_stat_rows, :] = df.loc[non_stat_rows, :].fillna(0)

    return df


def remove_stats(df: pd.DataFrame):
    stat_labels = list(stats_template.keys())
    idx = df.index
    if isinstance(idx, pd.MultiIndex) and idx.nlevels > 1:
        # MultiIndex: drop from last level
        return df.drop(
            index=[label for label in stat_labels if label in idx.get_level_values(-1)],
            level=-1,
        )
    else:
        # Single-level Index: drop by label
        return df.drop(index=[label for label in stat_labels if label in idx])


def iterate_statistical_groups(df: pd.DataFrame):
    col_idx = df.columns
    group_keys = col_idx.droplevel(-1).unique()
    for group_key in group_keys:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        columns_for_group = df.loc[:, pd.IndexSlice[group_key + (slice(None),)]]
        yield group_key, columns_for_group


def iterate_index_groups(df: pd.DataFrame):
    idx = df.index
    if idx.nlevels < 2:
        yield None, df
        return
    group_keys = idx.droplevel(-1).unique()
    for group_key in group_keys:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        idxer = pd.IndexSlice[group_key + (slice(None),)]
        group_df = df.loc[idxer, :]
        yield group_key, group_df  # No droplevel here!


def add_letter_level(group_df: pd.DataFrame) -> pd.DataFrame:
    n_cols = group_df.shape[1]
    # Generate Excel-style letters
    excel_letters = [f"({column_letters(i + 1)})" for i in range(n_cols)]
    # Add as a new last column level
    new_columns = pd.MultiIndex.from_tuples(
        [col + (letter,) for col, letter in zip(group_df.columns, excel_letters)],
        names=list(group_df.columns.names) + [None],
    )
    group_df.columns = new_columns
    return group_df


def add_letter_level_per_group(df: pd.DataFrame, group_levels=None):
    if not isinstance(df.columns, pd.MultiIndex):
        return add_letter_level(df)
    if group_levels is None:
        group_levels = df.columns.names[:-1]  # all except last

    # Build new columns with letters per group
    new_columns = []
    for group_key in df.columns.droplevel(-1).unique():
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        cols = df.loc[:, pd.IndexSlice[group_key + (slice(None),)]].columns
        n_cols = len(cols)
        letters = [f"({column_letters(i + 1)})" for i in range(n_cols)]
        for col, letter in zip(cols, letters):
            new_columns.append(col + (letter,))
    # Set new MultiIndex
    df.columns = pd.MultiIndex.from_tuples(
        new_columns, names=list(df.columns.names) + [None]
    )
    return df


def drop_column_levels(df: pd.DataFrame) -> pd.DataFrame:
    # drop levels of the columns
    if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
        # Keep only the last level
        levels_to_drop = list(range(df.columns.nlevels - 1))
        df.columns = df.columns.droplevel(levels_to_drop)
    return df


def compose_statistical_significance_df(
    col_group_df: pd.DataFrame,
    inner_df: pd.DataFrame,
    idx_group_key: tuple,
    col_identifier_func: Callable,
):
    # create a letters_inner_dict where the key is the value of the last level of the header and the letter is the value
    col_identifiers = [
        col_identifier_func(i + 1) for i in range(len(col_group_df.columns))
    ]

    # dictionary where the keys should be the every multiindex column name and the value should be the letter
    col_identifiers_inner_dict = {
        col_group_df.columns.to_list()[i]: col_identifiers[i]
        for i in range(len(col_group_df.columns))
    }

    statistical_significance = significant_differences(
        inner_df,
        col_group_df,
        tuple(list(idx_group_key) + ["Total"]),
        col_identifiers_inner_dict,
    )

    return statistical_significance


def get_inner_statistical_significance(
    df_percentage: pd.DataFrame,
    idx_group_df: pd.DataFrame,
    idx_group_key: tuple,
    col_identifier_func: Callable,
    levels_order: list[int] = None,
):
    for col_group_key, col_group_df in iterate_statistical_groups(idx_group_df):
        inner_df = remove_stats(col_group_df)
        statistical_significance = compose_statistical_significance_df(
            col_group_df, inner_df, idx_group_key, col_identifier_func
        )
        if levels_order:
            statistical_significance = reorder_header_levels(
                statistical_significance, levels_order
            )
        percentage_inner_df = df_percentage.loc[inner_df.index]

        contingency_table_percentage = concat_update(
            percentage_inner_df,
            statistical_significance,
        )

        df_percentage.update(contingency_table_percentage)

    return df_percentage


def concatenate_statistical_significance(
    df_count: pd.DataFrame,
    df_percentage: pd.DataFrame,
) -> pd.DataFrame:
    df_count_moment = reorder_header_levels(df_count, [1, 2, 0])

    for (idx_group_key, idx_group_df), (
        idx_group_key_moment,
        idx_group_df_moment,
    ) in zip(iterate_index_groups(df_count), iterate_index_groups(df_count_moment)):
        df_percentage = get_inner_statistical_significance(
            df_percentage,
            idx_group_df,
            idx_group_key,
            column_letters,
        )

        df_percentage = get_inner_statistical_significance(
            df_percentage, idx_group_df_moment, idx_group_key_moment, roman, [2, 0, 1]
        )

    return df_percentage


@st.cache_data(show_spinner=False)
def build_statistical_significance_df(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    cross_variables: list[str],
    selected_questions: list[str],
    config: dict,
    questions_by_group: dict[str, list[str]],
    view_type: Literal["Grouped", "Detailed"] = "Detailed",
    show_question_text: bool = False,
) -> pd.DataFrame:
    parsed_questions = parse_question_codes(db.columns, metadata_df)

    cross_questions_codes = get_cross_questions_codes(
        cross_variables, config, parsed_questions, for_="grids"
    ) + get_cross_questions_codes(
        cross_variables, config, parsed_questions, for_="filters"
    )
    selected_questions_codes = get_question_codes(
        selected_questions, questions_by_group
    )
    selected_questions_codes = get_related_question_codes(
        selected_questions_codes, parsed_questions
    )

    question_tables_count = []

    for selected_question, (question_label, question_codes) in zip(
        selected_questions, selected_questions_codes.items()
    ):
        question_composed_count_dfs = []

        question_count_with_visit = []

        for question_code in question_codes:
            try:
                contingency_tables_count = build_cross_contingency_table(
                    db,
                    metadata_df,
                    cross_questions_codes,
                    cross_variables,
                    question_code,
                    selected_question,
                    view_type,
                    questions_by_group,
                )

                question_composed_count_df = pd.concat(contingency_tables_count, axis=1)

                # Add question label as the first level of the index
                question_composed_count_df.index = pd.MultiIndex.from_product(
                    [[question_label], question_composed_count_df.index]
                )

                # convert the index to string
                question_composed_count_df.index = question_composed_count_df.index.map(
                    lambda x: tuple(str(i) for i in x)
                )

                question_composed_count_dfs.append(question_composed_count_df)

            except Exception:
                st.error(f"An error occurred processing question `{question_label}`")
                st.error(f"```\n{traceback.format_exc()}\n```")
                continue

        if question_composed_count_dfs:
            # Before concatenation, add the visit as a new level to each DataFrame's columns
            question_count_with_visit = []
            seen = set()
            repeated = set()
            for question_code, df_count in zip(
                question_codes,
                question_composed_count_dfs,
            ):
                question_code_parts = question_code.split("_")
                composed_variable = "_".join(question_code_parts[:2])
                if len(question_code_parts) > 2 and composed_variable in seen:
                    repeated.add(composed_variable)
                    continue
                seen.add(composed_variable)
                if len(question_code_parts) == 1:
                    visit = "V1"
                else:
                    visit = question_code_parts[1]  # e.g., 'V1'

                if isinstance(df_count.columns, pd.MultiIndex):
                    new_columns = pd.MultiIndex.from_tuples(
                        [(visit, *col) for col in df_count.columns]
                    )
                else:
                    new_columns = pd.MultiIndex.from_tuples(
                        [(visit, col) for col in df_count.columns]
                    )
                df_count.columns = new_columns
                question_count_with_visit.append(df_count)
            if len(repeated) > 0:
                st.warning(
                    f"The variable `{question_label}`"
                    " has been processed multiple times. "
                    "Only the first instance will be processed and shown."
                )
            if len(question_count_with_visit) > 1:
                column_lists = [
                    tuple(df.columns.tolist()) for df in question_count_with_visit
                ]
                all_columns_same = len(set(column_lists)) == 1
                question_table_count = question_count_with_visit[0].copy()
                if not all_columns_same:
                    for df in question_count_with_visit[1:]:
                        index_order = question_table_count.index.tolist()
                        question_table_count = question_table_count.merge(
                            df,
                            how="outer",
                            left_index=True,
                            right_index=True,
                            sort=False,
                        )
                        question_table_count = question_table_count.reindex(
                            index_order, axis=0
                        )
                else:
                    for df in question_count_with_visit[1:]:
                        question_table_count = question_table_count.combine_first(df)
            else:
                question_table_count = pd.concat(question_count_with_visit, axis=1)
        else:
            continue

        question_tables_count.append(question_table_count)

    final_tables = []

    for selected_question, question_table_count in zip(
        selected_questions, question_tables_count
    ):
        group, label = selected_question.split(" | ")
        group_questions = questions_by_group[group]

        question_config = list(
            filter(lambda d: d.get("label") == label, group_questions)
        )

        if question_config:
            question_config = question_config[0]
            question_type_config = get_question_type(
                question_config["question_type_id"]
            )

            if group == "FILTERS":
                question_table_count = sort_question_table(
                    question_table_count, question_config, question_type_config
                )

            if view_type == "Grouped":
                question_table_count = question_table_count.drop(
                    columns=[
                        col
                        for col in question_table_count.columns
                        if col[1] == "TOTAL" and col[2] == "TOTAL"
                    ]
                )

            # Create three-level multiindex
            new_index = []

            for i in range(len(question_table_count)):
                first_level = question_table_count.index[i][0]
                second_level = question_table_count.index[i][1]

                composed_label = (
                    f"{label} - {first_level}" if show_question_text else label
                )

                new_index.append((group, composed_label, second_level))

            question_table_count.index = pd.MultiIndex.from_tuples(new_index)

            final_tables.append(question_table_count)

    final_table_count = pd.concat(final_tables).fillna(0)

    final_table_count.index.names = ["Group", "Question", "Options"]

    final_table_percentage = get_percentage_df(final_table_count)

    concatenate_statistical_significance(
        final_table_count,
        final_table_percentage,
    )

    if view_type == "Grouped":
        # Drop all rows that are stats in the last level of the index
        final_table_percentage = remove_stats(final_table_percentage)

    final_table_percentage = add_letter_level_per_group(final_table_percentage)

    return final_table_percentage


def format_mixed_cell(x, decimal_precision: int):
    # Only try to match if x is a string
    if isinstance(x, str):
        match = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s+(.+)$", x)
        if match:
            num, s = match.groups()
            num = round(float(num), decimal_precision)
            if decimal_precision == 0 or num % 1 == 0:
                num_str = "{:d}".format(int(num))
            else:
                num_str = f"{num:,.{decimal_precision}f}"

            # Tokenize by spaces and classify
            tokens = s.split()
            letters = []
            romans = []
            if len(tokens) == 1:
                token_clean = tokens[0].replace(",", "")
                if re.fullmatch(r"[IVXL]+", token_clean):
                    romans.append(tokens[0])
                elif re.fullmatch(r"[A-Za-z,]+", tokens[0]):
                    letters.append(tokens[0])
                else:
                    letters.append(tokens[0])  # fallback
            else:
                for i, token in enumerate(tokens):
                    # Remove commas for classification, but keep for display
                    token_clean = token.replace(",", "")
                    if i == 0:
                        if re.fullmatch(r"[A-Za-z,]+", token_clean):
                            letters.append(token)
                    else:
                        if re.fullmatch(r"[IVXLCDM]+", token_clean):
                            romans.append(token)

            out = []
            if letters:
                out.append(
                    f"<span style='color: #ff4d4d; background: #fff0f0; border-radius: 3px; padding: 1px 3px'>{' '.join(letters)}</span>"
                )
            if romans:
                out.append(
                    f"<span style='color: #2563eb; background: #e0f2ff; border-radius: 3px; padding: 1px 3px'>{' '.join(romans)}</span>"
                )
            s = " ".join(out)
            return f"{num_str} {s}"
        else:
            try:
                num = float(x)
            except Exception:
                return x
            num = round(num, decimal_precision)
            if decimal_precision == 0 or num % 1 == 0:
                return "{:d}".format(int(num))
            else:
                return f"{num:,.{decimal_precision}f}"
    elif isinstance(x, (int, float)):
        num = round(float(x), decimal_precision)
        if decimal_precision == 0 or num % 1 == 0:
            return "{:d}".format(int(num))
        else:
            return f"{num:,.{decimal_precision}f}"
    else:
        return x


def create_html_table(df: pd.DataFrame, decimal_precision: int) -> str:
    nlevels = df.columns.nlevels
    row_height = 38  # px
    sticky_css = ""
    # Sticky column header CSS (as before)
    for i in range(nlevels + 3):
        top = i * row_height
        # Increase z-index with each header row to avoid overlap
        z_index = 10 + nlevels - i
        sticky_css += (
            f"thead tr:nth-child({i + 1}) th {{"
            f"position: sticky; top: {top}px; background: #222; color: #fff; z-index: {z_index}; "
            "border-bottom: 1px solid #888; border-top: 1px solid #888;"
            f"}}"
        )

    css = (
        "<style>"
        ".sticky-table-container {max-height: 600px; overflow-y: auto; width: 100%; border: 1px solid #ccc; margin: 10px 0;}"
        "table {border-collapse: separate; border-spacing: 0; width: 100%; font-size: 16px; color: inherit; border: 1px solid #ddd;}"
        "th { border: 1px solid #ddd !important; position: sticky; height: 38px; min-height: 38px; max-height: 38px; padding: 8px 4px; background: #222; color: #fff; box-sizing: border-box; margin: 0; }"
        "th, td {border: 1px solid #ddd !important; padding: 8px !important; text-align: center !important;}"
        "tr { text-align: center !important; margin: 0; }"
        f"{sticky_css}"
        "</style>"
    )

    html_table = (
        df.style.format(lambda x: format_mixed_cell(x, decimal_precision))
        .set_table_styles(table_styles)
        .to_html(escape=False, border=5)
    )
    return f"{css}<div class='sticky-table-container'>{html_table}</div>"
