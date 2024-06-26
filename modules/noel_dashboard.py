from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st

from modules.cloud import SharePoint

@st.cache_data
def get_data():

    share_point = SharePoint()

    # Path to the Excel file in SharePoint
    file_path = 'Documentos compartidos/dbs/norma_noel.xlsx'

    file_content = share_point.download_file(file_path)

    data = pd.read_excel(file_content)

    transformed_data = data.melt(
        id_vars=data.columns[:16],
        value_vars=data.columns[16:]
    ).dropna(subset='value').reset_index(drop=True)

    transformed_data['Categoría'] = transformed_data['Categoría'].apply(lambda x: x.strip())
    transformed_data['sample'] = transformed_data['sample'].astype(str)
    transformed_data['Género'] = transformed_data['Género'].astype(str)
    transformed_data['Edad'] = transformed_data['Edad'].apply(lambda x: x if isinstance(x, (float, int)) else np.nan)
    transformed_data['Estrato/Nivel socieconómico'] = transformed_data['Estrato/Nivel socieconómico'].astype(str)
    transformed_data['País'] = transformed_data['País'].apply(lambda x: x.capitalize())

    return transformed_data

# Function to convert DataFrame to Excel and return as bytes
def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Sheet1')
    return output.getvalue()

def calculate_statistics_jr_scale(data: pd.DataFrame, query: str | None = None):

    if query:
        data = data.query(query)

    # data.query("`Número del estudio` == 6428")

    statistics_data = pd.DataFrame()

    indexed_data = data.set_index(data.columns[:-2].to_list())
    indexed_data = indexed_data[indexed_data['value'].apply(lambda x: isinstance(x, float))]
    indexed_data['value'] = indexed_data['value'].astype(int)

    indexed_data = indexed_data[indexed_data['variable'].str.contains('JR')]

    statistics_data['base'] = indexed_data.groupby(['variable']).count()
    statistics_data['mean'] = indexed_data.groupby(['variable']).mean()
    statistics_data['std'] = indexed_data.groupby(['variable']).std()

    # JR
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'] == 3].rename(columns={'value': 'JR'}).groupby(['variable']).count(),
        left_index=True,
        right_index=True
    )
    statistics_data['%JR'] = statistics_data['JR'] / statistics_data['base']

    return statistics_data

def calculate_statistics_regular_scale(data: pd.DataFrame, query: str | None = None):

    if query:
        data = data.query(query)

    # data.query("`Número del estudio` == 6428")

    statistics_data = pd.DataFrame()

    indexed_data = data.set_index(data.columns[:-2].to_list())
    indexed_data = indexed_data[indexed_data['value'].apply(lambda x: isinstance(x, (float, int)))]
    indexed_data['value'] = indexed_data['value'].astype(int)

    indexed_data = indexed_data[~indexed_data['variable'].str.contains('JR')]

    statistics_data['base'] = indexed_data.groupby(['variable']).count()
    statistics_data['mean'] = indexed_data.groupby(['variable']).mean()
    statistics_data['std'] = indexed_data.groupby(['variable']).std()

    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'] == 5].rename(columns={'value': 'TB'}).groupby(['variable']).count(),
        left_index=True,
        right_index=True
    )
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'].isin([4, 5])].rename(columns={'value': 'T2B'}).groupby(['variable']).count(),
        left_index=True,
        right_index=True
    )
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'].isin([1, 2])].rename(columns={'value': 'B2B'}).groupby(['variable']).count(),
        left_index=True,
        right_index=True
    )

    statistics_data['%TB'] = statistics_data['TB'] / statistics_data['base']
    statistics_data['%T2B'] = statistics_data['T2B'] / statistics_data['base']
    statistics_data['%B2B'] = statistics_data['B2B'] / statistics_data['base']

    return statistics_data
