from io import BytesIO
import tempfile
from unidecode import unidecode
import pyreadstat
import numpy as np
import pandas as pd


def prepare_variable_mapping(file_name_xlsx: str, file_name_sav: str):

    metadata_db = pyreadstat.read_sav(file_name_sav)[1]
    variable_mapping = pd.read_excel(file_name_xlsx, sheet_name='MAPEO')

    time_columns = [col for col in variable_mapping.columns if col.startswith('time') and col != 'time_0']

    for col in time_columns:
        variable_mapping.loc[variable_mapping.index[-6:], col] = variable_mapping['time_0'].tail(6).values

    inverted_gender = variable_mapping['time_0'].tail(1).values[0]

    # connecta_study_value: belcorp_norma_values
    if inverted_gender:
        gender_equivalences = {1: 2, 2: 1}
    else:
        gender_equivalences = {1: 1, 2: 2}

    nse_equivalences = {
        'colombia': {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: ''},
        'mexico': {1: 15, 2: 16, 3: 17, 4: 18, 5: 19, 6: 20, 7: 21}
    }

    variable_mapping = variable_mapping.drop(variable_mapping.tail(1).index)

    variable_mapping['values'] = np.where(
        variable_mapping['belcorp'].isin(['IDCUEST', 'EDAD']),
        None,
        np.where(
            variable_mapping['belcorp'] == 'GENERO',
            gender_equivalences,
            np.where(
                variable_mapping['belcorp'] == 'NSE',
                nse_equivalences,
                np.where(
                    variable_mapping['belcorp'] == 'ALTERNATIVA',
                    metadata_db.variable_value_labels[variable_mapping.iloc[-1, 1]],
                    None
                )
            )
        )
    )

    return variable_mapping

def separate_moments(variable_mapping: pd.DataFrame, df_db: pd.DataFrame):
    df_list = []
    indexes = variable_mapping[variable_mapping['belcorp'].isin(variable_mapping['belcorp'].tail(5).values[:-1])]['time_0'].values.tolist()

    for i, moment in enumerate(variable_mapping.columns[variable_mapping.columns.str.startswith('time')]):
        df_moment = df_db[variable_mapping[moment].dropna().values].set_index(indexes)
        df_moment['MOMENTO'] = i + 1
        df_list.append(df_moment.reset_index())

    return df_list

def get_sav_db(file_name_sav: str):
    df_db: pd.DataFrame = pyreadstat.read_sav(file_name_sav)[0]
    df_db = df_db.dropna(axis=1, how='all')
    for column in df_db:
        df_db[column] = df_db[column].astype(int, errors='ignore')
    return df_db

def get_specifications(file_name_xlsx: str):
    specifications = pd.read_excel(file_name_xlsx, sheet_name='ESPECIFICACIONES', header=None)
    specifications[0] = specifications[0].apply(unidecode)
    return specifications

def transform(
    country: str,
    df_list: list[pd.DataFrame],
    variable_mapping: pd.DataFrame,
    specifications: pd.DataFrame,
    metadata_norma
):

    transformed_df_list = []
    moment_list = variable_mapping.columns[variable_mapping.columns.str.startswith('time')].to_list()

    for moment, moment_df in zip(moment_list, df_list):
        column_equivalences = {variable[moment]: variable['belcorp'] for i, variable in variable_mapping.iterrows() if variable[moment] is not np.nan}
        moment_df.rename(columns=column_equivalences, inplace=True)
        transformed_df_list.append(moment_df)

    transformed_df = pd.concat(transformed_df_list).reset_index(drop=True)

    for column in transformed_df:
        if column == 'MOMENTO':
            continue

        values_equivalences = variable_mapping[variable_mapping['belcorp'] == column]['values'].values[0]

        if values_equivalences:
            if column == 'NSE':
                values_equivalences = values_equivalences[country]
            transformed_df[column] = transformed_df[column].map(values_equivalences)

    columns = metadata_norma.column_names

    transformed_df['TIPO_NORMA'] = specifications[specifications[0] == 'TIPO DE NORMA'][1].values[0]
    transformed_df['ID_ESTUDIO'] = specifications[specifications[0] == 'ID ESTUDIO'][1].values[0]
    transformed_df['COD_CUC'] = specifications[specifications[0] == 'Codigo CUC del producto'][1].values[0]
    transformed_df['NOMBRE_ESTUDIO'] = specifications[specifications[0] == 'NOMBRE DEL ESTUDIO'][1].values[0]
    transformed_df['PAIS'] = next((key for key, value in metadata_norma.variable_value_labels['PAIS'].items() if unidecode(value.lower()) == country), None)
    transformed_df['ANO'] = specifications[specifications[0] == unidecode('AÑO')][1].values[0]
    transformed_df['MARCA'] = next((key for key, value in metadata_norma.variable_value_labels['MARCA'].items() if value == specifications[specifications[0] == 'MARCA'][1].values[0]), None)
    transformed_df['CATEGORIA'] = next((key for key, value in metadata_norma.variable_value_labels['CATEGORIA'].items() if value == specifications[specifications[0] == unidecode('CATEGORÍA DE PRODUCTO')][1].values[0]), None)
    transformed_df['TIPO'] = next((key for key, value in metadata_norma.variable_value_labels['TIPO'].items() if value == specifications[specifications[0] == 'TIPO DE PRODUCTO'][1].values[0]), None)
    transformed_df['RUTA'] = next((key for key, value in metadata_norma.variable_value_labels['RUTA'].items() if value == specifications[specifications[0] == 'RUTA CUESTIONARIO'][1].values[0]), None)

    brands = {unidecode(brand[1]).strip(): brand[3].strip() for _, brand in specifications[specifications[0].str.contains('ALTERNATIVA')].iterrows()}

    transformed_df['MARCA_ALT'] = transformed_df['ALTERNATIVA'].apply(lambda x: x.split('-')[0]).map(brands)
    alternative_brand = {y: x for x, y in metadata_norma.variable_value_labels['MARCA_ALT'].items()}

    transformed_df['MARCA_ALT'] = transformed_df['MARCA_ALT'].map(alternative_brand)
    transformed_df = transformed_df.dropna(subset=['MARCA_ALT']).reset_index(drop=True)
    transformed_df['MARCA_ALT'] = transformed_df['MARCA_ALT'].astype(int)
    transformed_df['NSE'] = transformed_df['NSE'].astype(int)
    transformed_df['IDCUEST'] = transformed_df['IDCUEST'].astype(int)
    transformed_df['ID_ESTUDIO'] = transformed_df['ID_ESTUDIO'].astype(int)
    transformed_df = transformed_df.reindex(columns=list(set([*transformed_df.columns, *columns])))
    transformed_df = transformed_df[columns]
    numeric_columns = [column for column in metadata_norma.variable_value_labels.keys() if column in metadata_norma.column_names]

    for column in numeric_columns:
        transformed_df[column] = transformed_df[column].astype(int, errors='ignore')

    return transformed_df

def get_temp_file(spss_file: BytesIO):
    # Save BytesIO object to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(spss_file.getvalue())
        temp_file_name = tmp_file.name

    return temp_file_name

def write_temp_sav(df: pd.DataFrame, metadata):
    with tempfile.NamedTemporaryFile() as tmpfile:
        # Write the DataFrame to the temporary SPSS file
        pyreadstat.write_sav(
            df,
            tmpfile.name,
            column_labels=metadata.column_names_to_labels,
            variable_value_labels=metadata.variable_value_labels
        )

        with open(tmpfile.name, 'rb') as f:
            return BytesIO(f.read())

def transform_to_belcorp(study: str, xlsx_file: BytesIO, sav_file: BytesIO):
    print('Started execution')

    temp_file_name_xlsx = get_temp_file(xlsx_file)
    temp_file_name_sav = get_temp_file(sav_file)

    variable_mapping = prepare_variable_mapping(temp_file_name_xlsx, temp_file_name_sav)
    df_db = get_sav_db(temp_file_name_sav)

    _, metadata_norma = pyreadstat.read_sav('static/templates/BBDD NORMAS - Plantilla.sav')

    df_list = separate_moments(variable_mapping, df_db)

    specifications = get_specifications(temp_file_name_xlsx)
    country = unidecode(specifications[specifications[0] == 'PAIS'][1].values[0].lower())

    df_final = transform(country, df_list, variable_mapping, specifications, metadata_norma)

    return write_temp_sav(df_final, metadata_norma)
