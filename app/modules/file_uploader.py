from io import BytesIO

from app.modules.cloud import SharePoint

import streamlit as st

@st.cache_data(show_spinner=False)
def get_sharepoint_studies(source: str):
    sharepoint = SharePoint()
    return sharepoint.list_folders(f'Documentos compartidos/{source}')


def upload_file_to_sharepoint(base_path: str, file_content: BytesIO, file_name: str):
    sharepoint = SharePoint()
    sharepoint.upload_file(base_path, file_content, file_name)

def get_last_file_version_in_sharepoint(id_study_name: str, source: str, file_path: str):
    sharepoint = SharePoint()
    return sharepoint.list_files(f'Documentos compartidos/{source}/{id_study_name}/{file_path}')


def check_sharepoint_folder_existance(id_study_name: str, source: str):
    sharepoint = SharePoint()
    studies_in_sharepoint = sharepoint.list_folders(f'Documentos compartidos/{source}')
    return id_study_name in studies_in_sharepoint
