from io import BytesIO
import tempfile

import pandas as pd
import pyreadstat

from firebase_admin import firestore

import streamlit as st

from app.modules.cloud import SharePoint

def get_temp_file(spss_file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(spss_file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name

def read_sav_metadata(file_name: str) -> pd.DataFrame:
    metadata =  pyreadstat.read_sav(
        file_name,
        apply_value_formats=False
    )[1]

    variable_info = pd.DataFrame([metadata.column_names_to_labels, metadata.variable_value_labels])
    variable_info = variable_info.transpose()
    variable_info.index.name = 'name'
    variable_info.columns = ('label', 'values')
    variable_info = variable_info.replace({None: ''})
    variable_info['label'] = variable_info['label'].astype(str)
    variable_info['values'] = variable_info['values'].astype(str)

    return variable_info

@st.cache_data(show_spinner=True)
def get_projects_info():
    db = firestore.client()
    document = db.collection("settings").document('projects_info').get()

    if document.exists:
        projects_info = document.to_dict()
        return projects_info

def create_folder_structure(base_path: str):

    # Define the directory structure
    dirs = [
        "codificacion/input",
        "codificacion/parcial",
        "generales/input",
        "generales/output/analisis",
        "generales/output/norma",
        "generales/output/tablas",
        "procesamiento/genera_axis",
        "procesamiento/includes",
        "procesamiento/quantum_files",
        "script/conceptos",
        "script/cuestionarios",
        "script/entrega_campo"
    ]

    sharepoint = SharePoint()

    studies_in_sharepoint = sharepoint.list_folders('Documentos compartidos/estudios')

    id_project_name = base_path.split('/')[-1]
    if id_project_name in studies_in_sharepoint:
        raise NameError('Combination of ID, country and study name alreday exists.')

    sharepoint.create_folder_structure(base_path, dirs)
