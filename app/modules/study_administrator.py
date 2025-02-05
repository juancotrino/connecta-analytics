import os
from io import BytesIO
import tempfile
from datetime import datetime
from pytz import timezone

import pandas as pd
import pyreadstat

from firebase_admin import firestore

from app.cloud.teams import (
    TeamsWebhook,
    AdaptiveCard,
    Container,
    FactSet,
    ContainerStyle,
    TextWeight,
    TextSize,
)

import streamlit as st

from app.cloud import SharePoint, BigQueryClient

time_zone = timezone("America/Bogota")


def get_temp_file(spss_file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(spss_file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name


def read_sav_metadata(file_name: str) -> pd.DataFrame:
    metadata = pyreadstat.read_sav(file_name, apply_value_formats=False)[1]

    variable_info = pd.DataFrame(
        [metadata.column_names_to_labels, metadata.variable_value_labels]
    )
    variable_info = variable_info.transpose()
    variable_info.index.name = "name"
    variable_info.columns = ("label", "values")
    variable_info = variable_info.replace({None: ""})
    variable_info["label"] = variable_info["label"].astype(str)
    variable_info["values"] = variable_info["values"].astype(str)

    return variable_info


def create_folder_structure(base_path: str):
    business_data = get_business_data()
    dirs = business_data["sharepoint_folder_structure"]

    sharepoint = SharePoint()

    studies_in_sharepoint = sharepoint.list_folders("Documentos compartidos/estudios")

    id_project_name = base_path.split("/")[-1]
    if id_project_name in studies_in_sharepoint:
        raise NameError("Combination of ID, country and study name alreday exists.")

    sharepoint.create_folder_structure(base_path, dirs)


@st.cache_data(show_spinner=False)
def get_studies(limit: int = 50, offset: int = 0, **kwargs):
    bq = BigQueryClient("business_data")

    # Dictionary mapping statuses to emojis
    status_emojis = {
        "Propuesta": "💡 Propuesta",
        "En ejecución": "🔨 En ejecución",
        "Cancelado": "❌ Cancelado",
        "No aprobado": "🚫 No aprobado",
        "Finalizado": "✅ Finalizado",
    }

    filters = ["study_id", "status", "country", "client", "methodology", "study_type"]
    kwargs_statements = []
    for _filter in filters:
        if kwargs.get(_filter):
            if _filter == "study_id":
                print("TEEEEEST", kwargs.get(_filter))
                filter_list = ", ".join(
                    [str(element) for element in kwargs.get(_filter)]
                )
                kwargs_statements.append(f"{_filter} IN ({filter_list})")
            else:
                filter_list = "', '".join(kwargs.get(_filter))
                kwargs_statements.append(f"{_filter} IN ('{filter_list}')")

    kwargs_query = " AND ".join(kwargs_statements)
    if kwargs_statements:
        kwargs_query = f"WHERE {kwargs_query}"

    query = f"""
        SELECT * FROM `{bq.schema_id}.{bq.data_set}.study`
        {kwargs_query}
        ORDER BY study_id DESC
        LIMIT {limit} OFFSET {offset}
    """
    print(query)
    studies_data = bq.fetch_data(query)

    studies_data["status"] = studies_data["status"].apply(
        lambda x: status_emojis.get(x, x)
    )
    studies_data = (
        studies_data.rename(columns={"study_id": "Study ID"})
        .set_index("Study ID")
        .sort_index(ascending=False)
    )
    studies_data["creation_date"] = (
        studies_data["creation_date"]
        .dt.tz_localize("UTC")
        .dt.tz_convert("America/Bogota")
        .dt.tz_localize(None)
    )
    studies_data["last_update_date"] = (
        studies_data["last_update_date"]
        .dt.tz_localize("UTC")
        .dt.tz_convert("America/Bogota")
        .dt.tz_localize(None)
    )

    return studies_data


@st.cache_data(show_spinner=False)
def get_business_data():
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()

    if document.exists:
        business_data = document.to_dict()
        return business_data


def get_last_id_number() -> int:
    bq = BigQueryClient("business_data")
    last_study_number = bq.fetch_data(
        f"""
        SELECT MAX(study_id) AS study_id FROM `{bq.schema_id}.{bq.data_set}.study`
        """
    )["study_id"][0]

    return last_study_number


def create_study_df(study_data: dict[str, list[int | str | float | datetime]]):
    study_data_df = pd.DataFrame(study_data)
    current_time = datetime.now(time_zone)
    study_data_df["creation_date"] = current_time
    study_data_df["last_update_date"] = current_time

    bq = BigQueryClient("business_data")
    bq.load_data("study", study_data_df)

    get_studies.clear()
    get_sudies_ids_country.clear()


@st.cache_data(show_spinner=False)
def get_sudies_ids_country():
    bq = BigQueryClient("business_data")
    return bq.fetch_data(
        f"""
        SELECT study_id, country, study_name FROM `{bq.schema_id}.{bq.data_set}.study`
        """
    )


@st.cache_data(show_spinner=False)
def get_study_data(study_id: int, country: str | None = None):
    bq = BigQueryClient("business_data")
    query = f"""
        SELECT * FROM `{bq.schema_id}.{bq.data_set}.study`
        WHERE study_id = {study_id}
    """
    if country:
        query += f" AND country = '{country}'"

    return bq.fetch_data(query)


@st.cache_data(show_spinner=False)
def get_number_of_studies(**kwargs) -> int:
    bq = BigQueryClient("business_data")

    filters = ["status", "country", "client", "methodology", "study_type"]
    kwargs_statements = []
    for _filter in filters:
        if kwargs.get(_filter):
            filter_list = "', '".join(kwargs.get(_filter))
            kwargs_statements.append(f"{_filter} IN ('{filter_list}')")

    kwargs_query = " AND ".join(kwargs_statements)

    if kwargs_statements:
        kwargs_query = f"WHERE {kwargs_query}"

    return bq.fetch_data(
        f"""
        SELECT COUNT(*) AS number_of_studies
        FROM `{bq.schema_id}.{bq.data_set}.study`
        {kwargs_query}
        """
    )["number_of_studies"].values[0]


def update_study_data(study_data: dict[str, str]):
    bq = BigQueryClient("business_data")

    bq.delete_data(
        f"""
        DELETE `{bq.schema_id}.{bq.data_set}.study`
        WHERE study_id = {study_data["study_id"][0]}
        """
    )

    study_data_df = pd.DataFrame(study_data)
    current_time = datetime.now(time_zone)
    study_data_df["last_update_date"] = current_time
    study_data_df["source"] = "app"

    bq.load_data("study", study_data_df)

    get_studies.clear()
    get_study_data.clear()


@st.cache_data(show_spinner=False, ttl=60)
def get_sharepoint_studies(source: str):
    sharepoint = SharePoint()
    return sharepoint.list_folders(f"Documentos compartidos/{source}")


@st.cache_data(show_spinner=False, ttl=60)
def get_upload_files_info():
    db = firestore.client()
    document = db.collection("settings").document("upload_files").get()

    if document.exists:
        files_info = dict(sorted(document.to_dict().items()))
        return files_info


def upload_file_to_sharepoint(base_path: str, file_content: BytesIO, file_name: str):
    sharepoint = SharePoint()
    sharepoint.upload_file(base_path, file_content, file_name)


def get_last_file_version_in_sharepoint(
    id_study_name: str, source: str, file_path: str
):
    sharepoint = SharePoint()
    return sharepoint.list_files(
        f"Documentos compartidos/{source}/{id_study_name}/{file_path}"
    )


def check_sharepoint_folder_existance(id_study_name: str, source: str):
    sharepoint = SharePoint()
    studies_in_sharepoint = sharepoint.list_folders(f"Documentos compartidos/{source}")
    return id_study_name in studies_in_sharepoint


@st.cache_data(show_spinner=False)
def split_frame(input_df, rows):
    df = [input_df.loc[i : i + rows - 1, :] for i in range(0, len(input_df), rows)]
    return df


def msteams_card_study_status_update(study_info: dict[str, str]):
    webhook = TeamsWebhook(os.getenv("MS_TEAMS_WEBHOOK_STUDY_STATUS_UPDATE"))

    card = AdaptiveCard(
        title="**STUDY STATUS UPDATE**", title_style=ContainerStyle.DEFAULT
    )

    container = Container(style=ContainerStyle.DEFAULT)

    container.add_text_block(
        f"Study **{study_info['study_id']} {study_info['study_name']}** changed its status to **{study_info['status']}** with these specifications:",
        size=TextSize.DEFAULT,
        weight=TextWeight.DEFAULT,
        color="default",
    )

    factset = FactSet()
    for k, v in study_info.items():
        if k not in ("study_folder", "status"):
            factset.add_facts((f"**{k.replace('_', ' ').capitalize()}**:", v))

    container.add_fact_set(factset)

    card.add_container(container)

    for country, study_folder in study_info["study_folder"].items():
        card.add_url_button(
            f"{country} study proposal folder", f"{study_folder}/consultoria/propuestas"
        )

    webhook.add_cards(card)
    webhook.send()


def msteams_card_file_update(file_name: str, study_info: dict[str, str]):
    webhook = TeamsWebhook(os.getenv(f"MS_TEAMS_WEBHOOK_{file_name.upper()}_UPDATE"))

    card = AdaptiveCard(
        title=f"**{file_name.replace('_', ' ').upper()} UPDATE**",
        title_style=ContainerStyle.DEFAULT,
    )

    container = Container(style=ContainerStyle.DEFAULT)

    container.add_text_block(
        f"Study **{study_info['study_id']} {study_info['study_name']}** has a new **{file_name.replace('_', ' ').title()}** file version:",
        size=TextSize.DEFAULT,
        weight=TextWeight.DEFAULT,
        color="default",
    )

    factset = FactSet()
    for k, v in study_info.items():
        if k not in ("file_folder"):
            factset.add_facts((f"**{k.replace('_', ' ').capitalize()}**:", v))

    container.add_fact_set(factset)

    card.add_container(container)

    card.add_url_button(
        f"{file_name.replace('_', ' ').title()} folder", study_info["file_folder"]
    )

    webhook.add_cards(card)
    webhook.send()
