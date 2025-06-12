from typing import Literal

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

import pandas as pd

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.cloud import CloudStorageClient
from app.modules.utils import get_countries, get_temp_file

cs_client = CloudStorageClient("connecta-app-1-service-processing")

db = firestore.client()


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


def get_cross_questions(config: dict) -> list[str]:
    return [question["label"] for question in config["cross_variables"]]


def get_cross_questions_codes(cross_questions: list[str], config: dict) -> list[str]:
    # Create a dictionary mapping labels to codes for efficient lookup
    label_to_code = {item["label"]: item["code"] for item in config["cross_variables"]}

    # Get codes for each target label
    return [label_to_code[label] for label in cross_questions if label in label_to_code]


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


def create_temp_df(
    selected_questions: list[str],
    questions_by_group: dict[str, str],
    data_option: int,
    view_type: str,
) -> pd.DataFrame:
    # Create a mapping of questions to their groups
    question_to_group = {}
    for group, questions in questions_by_group.items():
        for question in questions:
            question_to_group[question] = group

    if view_type == "Detailed":
        subindex = [
            "NETO TOP TWO BOX",
            "5. Muy dulce",
            "4.",
            "3.",
            "2.",
            "1. Nada dulce",
            "NETO BOTTOM TWO BOX",
            "Promedio:",
            "Desviación estándar:",
            "Error estándar:",
            "Total",
            "Total Respuestas",
            "%",
        ]

        # Group questions by their group
        questions_by_group = {}
        for question in selected_questions:
            if question in question_to_group:
                group = question_to_group[question]
                if group not in questions_by_group:
                    questions_by_group[group] = []
                questions_by_group[group].append(question)

        # Create MultiIndex for rows with group as first level
        index_tuples = []
        for group in sorted(questions_by_group.keys(), reverse=True):
            for question in questions_by_group[group]:
                for metric in subindex:
                    index_tuples.append((group, question, metric))

        multi_index = pd.MultiIndex.from_tuples(
            index_tuples, names=["Group", "Question", "Metric"]
        )

        # Calculate the number of rows needed for each column
        rows_per_column = len(multi_index)

        if data_option == 1:
            # Table 1
            data = {
                ("", "TOTAL", "(A)"): [
                    42,
                    19,
                    23,
                    36,
                    13,
                    9,
                    22,
                    3.29,
                    1.18,
                    0.02,
                    4783,
                    4783,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '42 <span style="color: red; font-weight: bold;">B</span>',  # 42 B
                    12,
                    '25 <span style="color: red; font-weight: bold;">A, B</span>',  # 25 B
                    40,
                    6,
                    18,
                    16,
                    3.36,
                    1.02,
                    0.02,
                    4189,
                    4189,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '35 <span style="color: red; font-weight: bold;">A</span>',  # 35 A
                    '27 <span style="color: red; font-weight: bold;">A</span>',  # 27 A
                    8,
                    14,
                    15,
                    '35 <span style="color: red; font-weight: bold;">A</span>',  # 35 A
                    '49 <span style="color: red; font-weight: bold;">A</span>',  # 49 A
                    2.78,
                    1.67,
                    0.07,
                    594,
                    594,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
            }
        else:
            # Table 2 (example with different numbers and letters)
            data = {
                ("", "TOTAL", "(A)"): [
                    50,
                    22,
                    30,
                    40,
                    10,
                    8,
                    18,
                    3.50,
                    1.10,
                    0.03,
                    5000,
                    5000,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '50 <span style="color: blue; font-weight: bold;">C</span>',  # 50 C
                    15,
                    '30 <span style="color: blue; font-weight: bold;">C</span>',  # 30 C
                    45,
                    7,
                    20,
                    18,
                    3.60,
                    1.05,
                    0.03,
                    4500,
                    4500,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '40 <span style="color: green; font-weight: bold;">D</span>',  # 40 D
                    '20 <span style="color: green; font-weight: bold;">D</span>',  # 20 D
                    10,
                    12,
                    18,
                    '40 <span style="color: green; font-weight: bold;">D</span>',  # 40 D
                    '55 <span style="color: green; font-weight: bold;">D</span>',  # 55 D
                    2.90,
                    1.70,
                    0.08,
                    600,
                    600,
                    100,
                ]
                * (rows_per_column // 13),  # Multiply by number of questions
            }
    else:
        subindex = ["TOP TWO BOX", "TOP BOX"]

        # Group questions by their group
        questions_by_group = {}
        for question in selected_questions:
            if question in question_to_group:
                group = question_to_group[question]
                if group not in questions_by_group:
                    questions_by_group[group] = []
                questions_by_group[group].append(question)

        # Create MultiIndex for rows with group as first level
        index_tuples = []
        for group in sorted(questions_by_group.keys(), reverse=True):
            for question in questions_by_group[group]:
                for metric in subindex:
                    index_tuples.append((group, question, metric))

        multi_index = pd.MultiIndex.from_tuples(
            index_tuples, names=["Group", "Question", "Metric"]
        )

        # Calculate the number of rows needed for each column
        rows_per_column = len(multi_index)

        if data_option == 1:
            # Table 1
            data = {
                ("", "TOTAL", "(A)"): [
                    42,
                    19,
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '42 <span style="color: red; font-weight: bold;">B</span>',  # 42 B
                    12,
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '35 <span style="color: red; font-weight: bold;">A</span>',  # 35 A
                    '27 <span style="color: red; font-weight: bold;">A</span>',  # 27 A
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
            }
        else:
            # Table 2 (example with different numbers and letters)
            data = {
                ("", "TOTAL", "(A)"): [
                    50,
                    22,
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '50 <span style="color: blue; font-weight: bold;">C</span>',  # 50 C
                    15,
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '40 <span style="color: green; font-weight: bold;">D</span>',  # 40 D
                    '20 <span style="color: green; font-weight: bold;">D</span>',  # 20 D
                ]
                * (rows_per_column // 2),  # Multiply by number of questions
            }

    return pd.DataFrame(data, index=multi_index)


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
    question_code: str, question_label: str, db: pd.DataFrame, metadata_df: pd.DataFrame
) -> pd.Series:
    mapping: dict = eval(metadata_df.loc[question_code]["values"])
    if len(mapping) == 1 and not next(iter(mapping.values())):
        return db[db.columns[db.columns.str.contains(question_code)][0]].astype(
            int
        )  # .rename()
    else:
        return db[db.columns[db.columns.str.contains(question_code)][0]].map(mapping)


def transform_cross_variable(
    cross_question_code: str,
    cross_question_label: str,
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.Series:
    mapping: dict = eval(metadata_df.loc[cross_question_code]["values"])
    return db[cross_question_code].map(mapping).rename(cross_question_label)


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

    reordered_df = df[new_columns]

    index_mapping: dict = eval(metadata_df.loc[question_code]["values"])

    if len(index_mapping) == 1 and not next(iter(index_mapping.values())):
        return reordered_df

    reordered_df = reordered_df.reindex(index_mapping.values())

    return reordered_df


@st.cache_data
def build_statistical_significance_df(
    db: pd.DataFrame,
    metadata_df: pd.DataFrame,
    cross_variables: list[str],
    selected_questions: list[str],
    config: dict,
    questions_by_group: dict[str, list[str]],
    decimal_precision: int = 0,
) -> pd.DataFrame:
    cross_questions_codes = get_cross_questions_codes(cross_variables, config)
    selected_questions_codes = get_question_codes(
        selected_questions, questions_by_group
    )

    selected_questions_codes = ["F2", "F15", "F17"]

    question_tables = []

    for question_code, question_label in zip(
        selected_questions_codes, selected_questions
    ):
        contingency_tables = []
        for i, (cross_question_code, cross_question_label) in enumerate(
            zip(cross_questions_codes, cross_variables)
        ):
            transformed_variable = transform_variable(
                question_code, question_label, db, metadata_df
            )
            transformed_cross_variable = transform_cross_variable(
                cross_question_code, cross_question_label, db, metadata_df
            )
            contingency_table = round(
                pd.crosstab(
                    transformed_variable,
                    transformed_cross_variable,
                    margins=True if i == 0 else False,
                    normalize="columns",
                )
                * 100,
                decimal_precision,
            )
            contingency_table = reorder_contingency_table(
                question_code, cross_question_code, contingency_table, metadata_df
            )

            # Generate the third level (A, B, C...)
            letters = [chr(65 + i) for i in range(len(contingency_table.columns))]

            # Create new column tuples
            new_column_tuples = []
            for j, col_name in enumerate(contingency_table.columns):
                new_column_tuples.append(
                    (cross_question_label, col_name, f"({letters[j]})")
                )

            contingency_table.columns = pd.MultiIndex.from_tuples(new_column_tuples)
            contingency_tables.append(contingency_table)
        question_composed_df = pd.concat(contingency_tables, axis=1)
        # Add question label as the first level of the index
        question_composed_df.index = pd.MultiIndex.from_product(
            [[question_label], question_composed_df.index]
        )
        question_tables.append(question_composed_df)

    final_table = pd.concat(question_tables)

    # Create three-level multiindex
    new_index = []
    for first_level, second_level in zip(
        final_table.index.get_level_values(0), final_table.index.get_level_values(1)
    ):
        group, question = first_level.split(" | ")
        new_index.append((group, question, second_level))

    final_table.index = pd.MultiIndex.from_tuples(new_index)
    final_table.index.names = ["Group", "Question", "Options"]

    return final_table
