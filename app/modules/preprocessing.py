from io import BytesIO
from zipfile import ZipFile
import tempfile

import numpy as np
import pandas as pd


def get_temp_file(file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        tmp_file.write(file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name

def write_temp_excel(wb):
    with tempfile.NamedTemporaryFile() as tmpfile:
        # Write the DataFrame to the temporary SPSS file
        wb.save(tmpfile.name)

        with open(tmpfile.name, 'rb') as f:
            return BytesIO(f.read())


def preprocessing(spss_file: BytesIO):

    # Create a BytesIO object to store the zip file
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        pass

    return write_temp_excel(spss_file)
