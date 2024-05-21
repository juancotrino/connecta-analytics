import os

def create_directory_structure(base_path):
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

    # Create each directory in the structure
    for dir in dirs:
        path = os.path.join(base_path, dir)
        os.makedirs(path, exist_ok=True)
        print(f"Created directory: {path}")
