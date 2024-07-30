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
        "script/entrega_campo",
        "consultoria/propuestas",
        "consultoria/informes",
        "consultoria/guias",
    ]

    sharepoint = SharePoint()

    studies_in_sharepoint = sharepoint.list_folders('Documentos compartidos/estudios')

    id_project_name = base_path.split('/')[-1]
    if id_project_name in studies_in_sharepoint:
        raise NameError('Combination of ID, country and study name alreday exists.')

    sharepoint.create_folder_structure(base_path, dirs)

def get_studies():
    from datetime import datetime

    # Dictionary mapping statuses to emojis
    status_emojis = {
        'Propuesta': '💡 Propuesta',
        'En ejecución': '🔨 En ejecución',
        'Cancelado': '❌ Cancelado',
        'No aprobado': '🚫 No aprobado',
        'Finalizado': '✅ Finalizado'
    }

    studies_data = pd.DataFrame(
        {
            'study_id': [1111, 2222, 3333, 4444, 5555],
            'study_name': ['test1', 'test2', 'test3', 'test4', 'test5'],
            'study_type': ['cualitativo', 'cuantitativo', 'informacion_secundaria', 'neuromaketing', 'cualitativo'],
            'description': ['description1', 'description2', '', 'description4', 'description5'],
            'country': ['colombia', 'colombia', 'colombia', 'mexico', 'ecuador'],
            'client': ['Noel', 'Noel', 'Belcorp', 'Noel', 'Nacional de Chocolates'],
            'value': [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000.54],
            'creation_date': [datetime(2021, 5, 12), datetime(2022, 1, 23), datetime(2022, 8, 2), datetime(2023, 2, 15), datetime(2024, 2, 26),],
            'last_update_date': [datetime(2021, 5, 12), datetime(2022, 1, 23), datetime(2022, 8, 2), datetime(2023, 2, 15), datetime(2024, 2, 26),],
            'supervisor': ['Juan', 'Alejandra', 'Valentina', 'Natalia', 'Maria'],
            'status': ['Propuesta', 'En ejecución', 'Cancelado', 'No aprobado', 'Finalizado'],
        }
    ).set_index('study_id')

    # Apply the emoji mapping to the 'status' column
    studies_data['study_name'] = studies_data['study_name'].str.replace('_', ' ').str.capitalize()
    studies_data['study_type'] = studies_data['study_type'].str.replace('_', ' ').str.capitalize()
    studies_data['description'] = studies_data['description'].str.replace('_', ' ').str.capitalize()
    studies_data['country'] = studies_data['country'].str.replace('_', ' ').str.capitalize()
    studies_data['status'] = studies_data['status'].apply(lambda x: status_emojis.get(x, x))

    return studies_data
