import os
from io import BytesIO
import json
import zipfile
import tempfile
import requests

import pandas as pd
import pyreadstat
from openpyxl import Workbook

import streamlit as st
from firebase_admin import firestore, auth

from app.modules.preprocessing import reorder_columns
from app.cloud.cloud_storage import CloudStorageClient


@st.cache_data(show_spinner=False)
def get_countries() -> dict[str, str]:
    url = "https://api.worldbank.org/v2/country?format=json&per_page=300&region=LCN"

    response = requests.get(url)

    if response.status_code == 200:
        countries_info = response.json()[1]

        country_names = [
            country["name"]
            for country in countries_info
            if "Latin America & Caribbean" in country["region"]["value"]
        ]
        countries_iso_2_code = {
            country["name"]: country["iso2Code"]
            for country in countries_info
            if country["name"] in country_names
        }

        return countries_iso_2_code

    else:
        return {"Colombia": "CO", "Mexico": "MX", "Ecuador": "EC", "Peru": "PE"}


def get_authorized_pages_names(pages_roles: dict):
    files = sorted(os.listdir("app/pages"))
    files_names = [file.split(".")[0] for file in files if not file.startswith("_")]
    pages_names = [" ".join(file_name.split("_")) for file_name in files_names]

    user_roles = st.session_state.get("roles")
    pages_to_show = []

    if user_roles:
        pages_to_show = [
            page
            for page in pages_names
            if any(
                role in pages_roles[page.replace(" ", "_")]["roles"]
                for role in user_roles
            )
        ]

    return pages_to_show


def get_temp_file(file: BytesIO, suffix: str | None = None):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name


def write_multiple_df_bytes(dfs_dict: dict[str, pd.DataFrame]) -> BytesIO:
    """
    Writes multiple DataFrames to an Excel file in memory.

    Args:
        dfs_dict (dict): A dictionary where the key is the sheet name and the value is a DataFrame.

    Returns:
        BytesIO: A BytesIO object containing the Excel file.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output


def write_bytes(data: pd.DataFrame | str, metadata=None):
    # Use a context manager with BytesIO
    bytes_io = BytesIO()

    if isinstance(data, pd.DataFrame) and not metadata:
        # Save the DataFrame to the BytesIO object
        data.to_excel(bytes_io, index=False)
    elif isinstance(data, str):
        # Write the combined output to the BytesIO object
        bytes_io.write(data.encode("utf-8"))
    elif isinstance(data, pd.DataFrame) and metadata:
        pyreadstat.write_sav(
            data,
            bytes_io,
            column_labels=metadata.column_names_to_labels,
            variable_value_labels=metadata.variable_value_labels,
        )

    # Reset the buffer's position to the beginning
    bytes_io.seek(0)

    return bytes_io


def read_sav_db(file_name: str, apply_value_formats: bool = False) -> pd.DataFrame:
    return pyreadstat.read_sav(file_name, apply_value_formats=apply_value_formats)[0]


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


def write_temp_sav(df: pd.DataFrame, metadata):
    variable_format = {column: "F20.0" for column in df.columns}
    variable_format.update(
        {column: "" for column in df.select_dtypes(include=["object"]).columns}
    )

    with tempfile.NamedTemporaryFile() as tmpfile:
        # Write the DataFrame to the temporary SPSS file
        pyreadstat.write_sav(
            df,
            tmpfile.name,
            column_labels=metadata.column_names_to_labels,
            variable_value_labels=metadata.variable_value_labels,
            variable_measure={column: "nominal" for column in df.columns},
            variable_format=variable_format,
        )

        with open(tmpfile.name, "rb") as f:
            return BytesIO(f.read())


def write_temp_excel(data: Workbook | pd.DataFrame, index: bool = False):
    with tempfile.NamedTemporaryFile() as tmpfile:
        if isinstance(data, Workbook):
            # Write the DataFrame to the temporary SPSS file
            data.save(tmpfile.name)
        elif isinstance(data, pd.DataFrame):
            data.to_excel(tmpfile, index=index)

        with open(tmpfile.name, "rb") as f:
            return BytesIO(f.read())


def try_download(
    label: str,
    data: BytesIO,
    file_name: str,
    file_extension: str,
    type: str = "primary",
):
    st.download_button(
        label=label,
        data=data.getvalue(),
        file_name=f"{file_name}.{file_extension}",
        mime=f"application/{file_extension}",
        type=type,
    )


def split_sav_file_to_chunks(file_name: str, max_records: int = 500):
    # Read the .sav file
    df, meta = pyreadstat.read_sav(file_name)

    # Calculate number of chunks
    num_chunks = (len(df) + max_records - 1) // max_records
    chunks = []

    # Split dataframe into chunks
    for i in range(num_chunks):
        start_idx = i * max_records
        end_idx = min((i + 1) * max_records, len(df))

        chunk = df.iloc[start_idx:end_idx]
        chunks.append(chunk)

    return chunks, meta


def create_zip_with_chunks(chunks: list[pd.DataFrame], meta, prefix: str):
    # Create a BytesIO stream for zip file
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, chunk in enumerate(chunks):
            # Write each chunk to a temporary BytesIO buffer
            chunk_buffer = write_temp_sav(chunk, meta)
            chunk_buffer.seek(0)

            # Add chunk to zip file
            zip_file.writestr(f"chunk_{i + 1}_{prefix}.sav", chunk_buffer.read())

    zip_buffer.seek(0)
    return zip_buffer


def join_sav(original_db_path: str, files_path: list[str]):
    original_db, original_meta = pyreadstat.read_sav(
        original_db_path, apply_value_formats=False
    )

    dfs = [
        pyreadstat.read_sav(file_path, apply_value_formats=False)[0]
        for file_path in files_path
    ]

    total_df = pd.concat(dfs).sort_values(by="Response_ID").reset_index(drop=True)
    total_df = total_df.drop(columns=["ABIERTAS", "ETIQUETAS"])

    last_numeric_var = get_last_numeric_var(original_db_path)
    final_df = reorder_columns(total_df, original_db, last_numeric_var)
    variable_format = {column: "F20.0" for column in final_df.columns}
    variable_format.update(
        {column: "" for column in final_df.select_dtypes(include=["object"]).columns}
    )

    return write_temp_sav(final_df, original_meta)


def get_last_numeric_var(original_db_path):
    original_db, original_meta = pyreadstat.read_sav(
        original_db_path, apply_value_formats=False
    )
    var_type_base = original_meta.original_variable_types  # F-- Float / A-- String

    last_num_var = ""
    for var in original_meta.column_names:
        if not var_type_base[var].startswith("A"):
            last_num_var = var
    return last_num_var


def load_json(path: str) -> dict:
    """
    Load a JSON file from a local path and return its contents as a dictionary.

    Args:
        path (str): The local path to the JSON file.

    Returns:
        dict: The contents of the JSON file.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False, ttl=600)
def get_inverted_scales_keywords():
    """Get inverted scales keywords from Firestore."""
    db = firestore.client()
    document = db.collection("settings").document("keywords").get()

    if document.exists:
        return document.to_dict()["inverted_scales"]
    else:
        return {"keywords": []}


def column_letters(n):
    letters = []
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


L = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def roman(num):
    if num == 0:  # Base case: when we reach zero, return empty string
        return ""
    # Recursive step: iterate over values and their characters
    for v, n in L:
        if num >= v:  # If their difference is positive, we recurse
            return n + roman(num - v)  # We append the result to the numeral


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


@st.cache_data(show_spinner=False)
def get_users() -> list:
    users = []
    page = auth.list_users()

    while page:
        for user in page.users:
            users.append(
                {
                    "user_id": user.uid,
                    "name": user.display_name,
                    "email": user.email,
                }
            )
        page = page.get_next_page()
    return users


def get_user_name_from_id(user_id: str) -> str:
    users = get_users()
    for user in users:
        if user["user_id"] == user_id:
            return user["name"]
    return None


def get_user_id_from_name(user_name: str) -> str:
    users = get_users()
    for user in users:
        if user["name"] == user_name:
            return user["user_id"]
    return None


def upload_to_gcs(source_file_name: str, destination_blob_name: str, bucket_name: str):
    gcs = CloudStorageClient(bucket_name)
    return gcs.upload_to_gcs(source_file_name, destination_blob_name)


def delete_gcs(blob_name: str, bucket_name: str):
    gcs = CloudStorageClient(bucket_name)
    gcs.delete_from_gcs(blob_name)


def upload_study_to_gcs(
    uploaded_file_sav: BytesIO,
    category: str,
    subcategory: str,
    country_code: str,
    company: str,
    study_id: str,
    study_name: str,
    extension: str,
):
    temp_file_name = get_temp_file(uploaded_file_sav, extension)
    file_name = f"{_to_code(study_id)}_{_to_code(study_name)}"
    blob_name = (
        f"databases/{category}/{subcategory}/{country_code}/"
        f"{company}/{file_name}.{extension}"
    )
    upload_to_gcs(temp_file_name, blob_name, "connecta-app-1-service-processing")
    # delete temp file
    os.unlink(temp_file_name)


def get_study_config(
    category: str,
    subcategory: str,
    country_code: str,
    company: str,
    study: str,
) -> dict:
    category = _to_code(category)
    subcategory = _to_code(subcategory)
    study_name = _to_code(study)
    blob_name = (
        f"databases/{category}/{subcategory}/{country_code}/{company}/{study_name}.json"
    )
    gcs = CloudStorageClient("connecta-app-1-service-processing")
    bytes_io = gcs.download_as_bytes(blob_name)
    # Read the bytes from BytesIO and decode to string before parsing JSON
    return json.loads(bytes_io.getvalue().decode("utf-8"))


@st.cache_data(show_spinner=False)
def get_companies_blobs(bucket_name: str) -> list[str]:
    gcs = CloudStorageClient(bucket_name)
    blobs = gcs.list_files("databases")
    return list(set([blob.split("/")[3] for blob in blobs if len(blob.split("/")) > 3]))
