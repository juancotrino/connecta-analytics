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
def get_group_id(
    group_name: str | None, category_id: str | None, subcategory_id: str | None
) -> str | None:
    if not group_name or not subcategory_id:
        return None

    group_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("groups")
        .where(filter=FieldFilter("name", "==", group_name))
        .where(filter=FieldFilter("category_id", "==", category_id))
        .where(filter=FieldFilter("subcategory_id", "==", subcategory_id))
        .limit(1)
        .stream()
    )
    for group_doc in group_query:
        return group_doc.id
    print(f"No group found with name: {group_name}")
    return None


@st.cache_data(show_spinner=False)
def get_questions(
    category_name: str | None = None,
    subcategory_name: str | None = None,
    group_name: str | None = None,
) -> list[dict[str, str]]:
    category_id = get_category_id(category_name)
    subcategory_id = get_subcategory_id(subcategory_name, category_id)
    group_id = get_group_id(group_name, category_id, subcategory_id)

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
    if group_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("group_id", "==", group_id)
        )

    questions_query = questions_ref.stream()
    questions = [question_doc.to_dict() for question_doc in questions_query]
    return questions


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
    selected_questions: list[str], data_option: int, view_type: str
) -> pd.DataFrame:
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

        # Create MultiIndex for rows
        multi_index = pd.MultiIndex.from_product([selected_questions, subindex])

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
                * len(selected_questions),
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
                * len(selected_questions),
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
                * len(selected_questions),
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
                * len(selected_questions),
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
                * len(selected_questions),
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
                * len(selected_questions),
            }
    else:
        subindex = ["TOP TWO BOX", "TOP BOX"]

        # Create MultiIndex for rows
        multi_index = pd.MultiIndex.from_product([selected_questions, subindex])
        if data_option == 1:
            # Table 1
            data = {
                ("", "TOTAL", "(A)"): [
                    42,
                    19,
                ]
                * len(selected_questions),
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '42 <span style="color: red; font-weight: bold;">B</span>',  # 42 B
                    12,
                ]
                * len(selected_questions),
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '35 <span style="color: red; font-weight: bold;">A</span>',  # 35 A
                    '27 <span style="color: red; font-weight: bold;">A</span>',  # 27 A
                ]
                * len(selected_questions),
            }
        else:
            # Table 2 (example with different numbers and letters)
            data = {
                ("", "TOTAL", "(A)"): [
                    50,
                    22,
                ]
                * len(selected_questions),
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "Si",
                    "(A)",
                ): [
                    '50 <span style="color: blue; font-weight: bold;">C</span>',  # 50 C
                    15,
                ]
                * len(selected_questions),
                (
                    "P23. ¿Te agrada el DULZOR de la fragancia que probaste?",
                    "No",
                    "(B)",
                ): [
                    '40 <span style="color: green; font-weight: bold;">D</span>',  # 40 D
                    '20 <span style="color: green; font-weight: bold;">D</span>',  # 20 D
                ]
                * len(selected_questions),
            }

    return pd.DataFrame(data, index=multi_index)
