from typing import Literal
import traceback

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

import pandas as pd
import ast

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.cloud import CloudStorageClient
from app.modules.utils import (
    get_countries,
    get_temp_file,
)

cs_client = CloudStorageClient("connecta-app-1-service-processing")

db = firestore.client()

# CSS to highlight headers and index of the dataframe
table_styles = [
    dict(selector="th", props="font-size: 1.0em; "),
    dict(selector="td", props="font-size: 1.0em; text-align: right"),
    dict(selector="tr:hover", props="background-color: #666666"),
]


@st.cache_data(show_spinner=False)
def get_business_data():
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()

    if document.exists:
        business_data = document.to_dict()
        return business_data


def _to_code(text: str) -> str:
    return text.lower().replace(" ", "_")


def _to_show(text: str, form: str = "capitalize") -> str:
    match form:
        case "capitalize":
            return text.replace("_", " ").capitalize()
        case "title":
            return text.replace("_", " ").title()
        case _:
            return text.replace("_", " ")


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
    group_name: list[str] | None = None,
    by: Literal["label", "code"] = "label",
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
    if not group_name:
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
        group_ids = get_group_ids(group_name, category_id, subcategory_id)

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

    all_groups = {doc.id: doc.to_dict()["name"] for doc in all_groups_ref.stream()}

    # Create a mapping of group_id to its index in the sorted groups
    group_order = {
        group_id: idx
        for idx, group_id in enumerate(
            sorted(all_groups.keys(), key=lambda x: all_groups[x], reverse=True)
        )
    }

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
        group_name = all_groups.get(group_id, "Unknown")
        if group_name not in grouped_questions:
            grouped_questions[group_name] = []
        grouped_questions[group_name].append(
            # question.get("label", "")
            {"label": question.get("label", ""), "code": question.get("code", "")}
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
    label_to_code = {item["label"]: item["code"] for item in config[key]}

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

    # Collect and return the group names
    group_names = [group_doc.to_dict().get("name") for group_doc in groups_query]
    return group_names


@st.cache_data(show_spinner=False)
def get_studies_names(
    category: str, subcategory: str, country: str, company: str
) -> list[str]:
    """Get studies names from files in storage bucket and transform them
    to show them in the UI."""
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    countries_iso = get_countries()
    country_code = countries_iso[country].lower()
    study_names = cs_client.list_files(
        f"databases/{category}/{subcategory}/{country_code}/{company}"
    )
    return list(
        set([_to_show(study_name.split(".")[0], "title") for study_name in study_names])
    )


@st.cache_data(show_spinner=False)
def get_study_countries(
    category: str,
    subcategory: str,
) -> list[str]:
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    countries_iso = get_countries()
    iso_countries = {iso: country for country, iso in countries_iso.items()}
    files = cs_client.list_files(f"databases/{category}/{subcategory}")
    study_countries = list(set([file.split("/")[0].upper() for file in files]))
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
    category: str, subcategory: str, country: str, company: str, studies: list[str]
) -> dict[str, dict[str, str]]:
    """Download the respective files (.sav, .json) from storage bucket for the
    selected studies."""
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    countries_iso = get_countries()
    country_code = countries_iso[country].lower()
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
) -> pd.DataFrame:
    column_mapping: dict = eval(metadata_df.loc[cross_question_code]["values"])
    new_columns = [
        column_name
        for column_name in column_mapping.values()
        if column_name in df.columns
    ]
    if "All" in df.columns:
        new_columns = ["All"] + new_columns

    reordered_df = df[new_columns]

    index_mapping: dict = eval(metadata_df.loc[question_code]["values"])

    if len(index_mapping) == 1 and not next(iter(index_mapping.values())):
        return reordered_df

    reordered_df = reordered_df.reindex(index_mapping.values())

    return reordered_df


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


def build_cross_contingency_table(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    cross_questions_codes: list[str],
    cross_variables: list[str],
    question_code: str,
    decimal_precision: int = 0,
) -> list[pd.DataFrame]:
    contingency_tables = []

    for i, (cross_question_code, cross_question_label) in enumerate(
        zip(cross_questions_codes, cross_variables)
    ):
        transformed_variable = transform_variable(question_code, db, metadata_df)
        sub_contingency_tables = []
        for j, sub_cross_question_code in enumerate(cross_question_code):
            transformed_cross_variable = transform_cross_variable(
                sub_cross_question_code, cross_question_label, db, metadata_df
            )

            contingency_table = round(
                pd.crosstab(
                    transformed_variable,
                    transformed_cross_variable,
                    margins=True if i == 0 and j == 0 else False,
                    normalize="columns",
                )
                * 100,
                decimal_precision,
            )

            contingency_table = reorder_contingency_table(
                question_code,
                sub_cross_question_code,
                contingency_table,
                metadata_df,
            )

            sub_contingency_tables.append(contingency_table)

            contingency_table = pd.concat(sub_contingency_tables, axis=1)

        # Generate the third level (A, B, C...)
        # Separate "All" column and assign letters to remaining columns
        new_column_tuples = []

        # Count non-"All" columns to generate appropriate letters
        non_all_columns = [col for col in contingency_table.columns if col != "All"]
        letters = [chr(65 + i) for i in range(len(non_all_columns))]

        for j, col_name in enumerate(contingency_table.columns):
            if col_name == "All":
                new_column_tuples.append(("TOTAL", "TOTAL", "(A)"))
            else:
                # Find the index of this column in the non-"All" columns list
                non_all_index = non_all_columns.index(col_name)
                new_column_tuples.append(
                    (cross_question_label, col_name, f"({letters[non_all_index]})")
                )

        contingency_table.columns = pd.MultiIndex.from_tuples(new_column_tuples)
        contingency_tables.append(contingency_table)

    return contingency_tables


def create_view_type_df(
    question_table: pd.DataFrame,
    view_type: Literal["Groupped", "Detailed"] = "Detailed",
) -> pd.DataFrame:
    if view_type == "Groupped":
        # Collapse the "Options" level
        options_level = -1

        options_values = question_table.index.get_level_values(options_level).astype(
            str
        )

        # T2B: sum all options starting with "4." or "5."
        t2b_mask = options_values.str.startswith("4.") | options_values.str.startswith(
            "5."
        )
        group_levels = list(range(question_table.index.nlevels - 1))
        t2b_df = (
            question_table[t2b_mask].groupby(level=group_levels).sum(numeric_only=True)
        )
        t2b_df["Options"] = "T2B"
        t2b_df = t2b_df.set_index("Options", append=True)
        if len(t2b_df.index.names) == len(question_table.index.names):
            t2b_df.index.names = question_table.index.names

        # TB: only options starting with "5."
        tb_mask = options_values.str.startswith("5.")
        tb_df = question_table[tb_mask].copy()
        # Rename all matching to "TB"
        tb_df = tb_df.rename(
            index={idx: "TB" for idx in tb_df.index.get_level_values(options_level)},
            level=options_level,
        )

        # Concatenate
        collapsed_table = pd.concat([t2b_df, tb_df]).sort_index()
        question_table = collapsed_table

    return question_table


# @st.cache_data(show_spinner=False)
def build_statistical_significance_df(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    cross_variables: list[str],
    selected_questions: list[str],
    config: dict,
    questions_by_group: dict[str, list[str]] | None = None,
    decimal_precision: int = 0,
    by_moment: bool = False,
    view_type: Literal["Groupped", "Detailed"] = "Detailed",
    show_question_text: bool = False,
) -> pd.DataFrame:
    parsed_questions = parse_question_codes(db.columns, metadata_df)

    if questions_by_group:
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

    else:
        cross_questions_codes = get_cross_questions_codes(
            cross_variables, config, parsed_questions, for_="filters"
        )
        selected_questions_codes = get_codes_by_labels(
            selected_questions, parsed_questions
        )

    question_tables = []

    for question_label, question_codes in selected_questions_codes.items():
        question_composed_dfs = []
        for question_code in question_codes:
            try:
                contingency_tables_cross = build_cross_contingency_table(
                    db,
                    metadata_df,
                    cross_questions_codes,
                    cross_variables,
                    question_code,
                    decimal_precision,
                )

                question_composed_df = pd.concat(contingency_tables_cross, axis=1)

                # Add question label as the first level of the index
                question_composed_df.index = pd.MultiIndex.from_product(
                    [[question_label], question_composed_df.index]
                )

                question_composed_dfs.append(question_composed_df)

            except Exception:
                st.error(f"An error occurred processing question `{question_label}`")
                st.error(f"```\n{traceback.format_exc()}\n```")
                continue

        if question_composed_dfs:
            if by_moment:
                # Before concatenation, add the visit as a new level to each DataFrame's columns
                dfs_with_visit = []
                for question_code, df in zip(question_codes, question_composed_dfs):
                    visit = question_code.split("_")[1]  # e.g., 'V1'
                    if isinstance(df.columns, pd.MultiIndex):
                        new_columns = pd.MultiIndex.from_tuples(
                            [(visit, *col) for col in df.columns]
                        )
                    else:
                        new_columns = pd.MultiIndex.from_tuples(
                            [(visit, col) for col in df.columns]
                        )
                    df.columns = new_columns
                    df = df.drop(columns=[(visit, "TOTAL", "TOTAL", "(A)")])

                    dfs_with_visit.append(df)

                question_table = pd.concat(dfs_with_visit, axis=1)

            else:
                question_table = pd.concat(question_composed_dfs)

            # TODO: Uncomment this to get from the config JSON for each question
            # the properties for sorting.
            # This should be a function where all config are applied to the table
            # like for example, adding the needed additional rows like total, average,
            # percentage, std, st error, T2B, TB, B2B, BB, etc
            # if ("TOTAL", "TOTAL", "(A)") in question_table.columns:
            #     question_table = question_table.sort_values(
            #         by=("TOTAL", "TOTAL", "(A)"), ascending=False
            #     )
            # Inside the next function should be handle that passing an additional
            # parameter with the question options or config
            question_table = create_view_type_df(question_table, view_type)

        else:
            continue

        question_tables.append(question_table)

    if questions_by_group:
        final_table = pd.concat(question_tables).fillna(0)
        # Create three-level multiindex
        new_index = []
        current = 0
        for selected_question in selected_questions:
            # Count how many rows this question has
            count = sum(
                1
                for i in range(current, len(final_table.index))
                if final_table.index[current][0] == final_table.index[i][0]
            )

            for i in range(count):
                first_level = final_table.index[current + i][0]
                second_level = final_table.index[current + i][1]
                group, question = selected_question.split(" | ")

                composed_label = (
                    f"{question} - {first_level}" if show_question_text else question
                )

                new_index.append((group, composed_label, second_level))
            current += count

        final_table.index = pd.MultiIndex.from_tuples(new_index)

        final_table.index.names = ["Group", "Question", "Options"]
    else:
        final_table = pd.concat(question_tables).dropna()
        final_table.index.names = ["Question", "Options"]

    return final_table


def create_html_table(df: pd.DataFrame, decimal_precision: int) -> str:
    return (
        df.style.format(
            lambda x: (
                "{:,.{}f}".format(x, decimal_precision)
                if isinstance(x, (float, int)) and x % 1 != 0
                else "{:d}".format(int(x))
                if isinstance(x, (float, int))
                else x
            )
        )
        .set_table_styles(table_styles)
        .to_html(escape=False, border=5)
    )
