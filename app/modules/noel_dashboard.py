from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st

from app.cloud import SharePoint, BigQueryClient

@st.cache_data(show_spinner=False)
def get_data_unique():
    bq = BigQueryClient('normas')
    return bq.fetch_data(
        """
        SELECT DISTINCT
            category,
            sub_category,
            client,
            study_name,
            brand,
            sample,
            age,
            gender,
            ses,
            country
        FROM `connecta-analytics-app.normas.estudios_externos`;
        """
    )

@st.cache_data
def get_data():

    share_point = SharePoint()

    # Path to the Excel file in SharePoint
    file_path = 'Documentos compartidos/dbs/norma_noel.xlsx'

    file_content = share_point.download_file(file_path)

    data = pd.read_excel(file_content)

    transformed_data = data.melt(
        id_vars=data.columns[:14],
        value_vars=data.columns[14:]
    ).dropna(subset='value').reset_index(drop=True)

    transformed_data['category'] = transformed_data['category'].apply(lambda x: x.strip())
    transformed_data['sample'] = transformed_data['sample'].astype(str)
    transformed_data['gender'] = transformed_data['gender'].astype(str)
    transformed_data['age'] = transformed_data['age'].apply(lambda x: x if isinstance(x, (float, int)) else np.nan)
    transformed_data['ses'] = transformed_data['ses'].astype(str)
    transformed_data['country'] = transformed_data['country'].apply(lambda x: x.capitalize())

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
    indexed_data = indexed_data[indexed_data['value'].apply(lambda x: isinstance(x, (float, int)))]
    indexed_data['value'] = indexed_data['value'].astype(int)

    indexed_data = indexed_data[indexed_data['attribute'].str.contains('JR')]

    statistics_data['base'] = indexed_data.groupby(['attribute']).count()
    statistics_data['mean'] = indexed_data.groupby(['attribute']).mean()
    statistics_data['std'] = indexed_data.groupby(['attribute']).std()

    # JR
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'] == 3].rename(columns={'value': 'JR'}).groupby(['attribute']).count(),
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

    indexed_data = indexed_data[~indexed_data['attribute'].str.contains('JR')]

    statistics_data['base'] = indexed_data.groupby(['attribute']).count()
    statistics_data['mean'] = indexed_data.groupby(['attribute']).mean()
    statistics_data['std'] = indexed_data.groupby(['attribute']).std()

    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'] == 5].rename(columns={'value': 'TB'}).groupby(['attribute']).count(),
        left_index=True,
        right_index=True
    )
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'].isin([4, 5])].rename(columns={'value': 'T2B'}).groupby(['attribute']).count(),
        left_index=True,
        right_index=True
    )
    statistics_data = pd.merge(
        statistics_data,
        indexed_data[indexed_data['value'].isin([1, 2])].rename(columns={'value': 'B2B'}).groupby(['attribute']).count(),
        left_index=True,
        right_index=True
    )

    statistics_data['%TB'] = statistics_data['TB'] / statistics_data['base']
    statistics_data['%T2B'] = statistics_data['T2B'] / statistics_data['base']
    statistics_data['%B2B'] = statistics_data['B2B'] / statistics_data['base']

    return statistics_data

def build_query(filters: dict[str, list[str | int]]) -> str:
    query = []
    for variable, options in filters.items():
        if variable == 'age' and options:
            sub_query = f'(({variable} >= {options[0]} AND {variable} <= {options[1]}) OR age IS NULL)'
            query.append(sub_query)
        else:
            if options:
                if options[0]:
                    if isinstance(options[0], str):
                        options_text = "', '".join(options)
                        sub_query = f"{variable} IN ('{options_text}')"
                        query.append(sub_query)

    return ' AND '.join(query)

@st.cache_data(show_spinner=False)
def get_filtered_data(query: str):

    bq = BigQueryClient('normas')

    return bq.fetch_data(
        """
        SELECT
            *
        FROM `connecta-analytics-app.normas.estudios_externos`
        WHERE {query};
        """.format(query=query)
    )
