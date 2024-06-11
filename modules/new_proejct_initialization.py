from modules.cloud import SharePoint

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
