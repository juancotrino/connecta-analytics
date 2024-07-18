import os
import io
from io import BytesIO
import tempfile
import zipfile
from copy import copy
from datetime import datetime
from pytz import timezone

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import openpyxl
from openpyxl.chart import BarChart, Reference
from openpyxl.utils.dataframe import dataframe_to_rows

import pyreadstat
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from app.modules.authenticator import get_inverted_scales_keywords

time_zone = timezone('America/Bogota')

scales = {
    'T2B':{
        'regular': {5: 1, 4: 1, 3: 0, 2: 0, 1: 0},
        'inverted': {1: 1, 2: 1, 3: 0, 4: 0, 5: 0},
        'just_right': {1: 0, 2: 0, 3: 1, 4: 0, 5: 0}
    },
    'TB': {
        'regular': {5: 1, 4: 0, 3: 0, 2: 0, 1: 0},
        'inverted': {1: 1, 2: 0, 3: 0, 4: 0, 5: 0},
        'just_right': {1: 0, 2: 0, 3: 1, 4: 0, 5: 0}
    }
}

# Function to perform chi-square test and return chi2, p-value, and Cramer's V
def chi_square_test(column1, column2, correction: bool = False):
    contingency_table = pd.crosstab(column1, column2)
    chi2, p_value, _, _ = chi2_contingency(contingency_table, correction=correction)
    n = contingency_table.sum().sum()
    phi2 = chi2 / n
    r, k = contingency_table.shape
    if correction:
        phi2corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
        rcorr = r - ((r - 1) ** 2) / (n - 1)
        kcorr = k - ((k - 1) ** 2) / (n - 1)
        return chi2, p_value, np.sqrt(phi2corr / min((kcorr - 1), (rcorr - 1)))
    else:
        return chi2, p_value, np.sqrt(phi2 / (k - 1)) if k > 1 else 0

def process_chi2(
    file_path: str,
    cross_variable: str,
    chi2_mode: str,
    inverted_scales_keywords: list,
    correction: bool = False,
):

    data, study_metadata = pyreadstat.read_sav(
        file_path,
        apply_value_formats=False
    )

    variables_data = study_metadata.variable_value_labels

    filtered_variables = [variable for variable, scale in variables_data.items() if len(scale) == 5]
    filtered_variables_data = {k: v for k, v in variables_data.items() if k in filtered_variables}

    just_right_variables = [code for code, tag in filtered_variables_data.items() if 'just' in ''.join(tag.values()).lower()]

    inverted_variables = [
        code for code, tag in filtered_variables_data.items()
        if any(
            keyword in ''.join(tag.values()).lower()
            for keyword in inverted_scales_keywords
        ) and (
            code not in just_right_variables
        )
    ]

    filtered_data: pd.DataFrame = data[data.columns[data.columns.isin(filtered_variables)]]
    filtered_data_bool = filtered_data.copy()

    variables_scale_info = pd.DataFrame(list(study_metadata.column_names_to_labels.items()), columns=['code', 'text']).replace({None: np.nan})

    variables_scale_info['scale_type'] = np.where(
        variables_scale_info['code'].isin(just_right_variables),
        'just_right',
        np.where(
            variables_scale_info['code'].isin(inverted_variables),
            'inverted',
            'regular'
        )
    )
    variables_scale_info['scale_type'] = variables_scale_info['scale_type'].replace({None: np.nan})

    for column in filtered_data:
        scale_type = variables_scale_info[variables_scale_info['code'] == column]['scale_type'].values[0]
        filtered_data_bool.loc[:, column] = filtered_data.loc[:, column].map(scales[chi2_mode][scale_type])

    # Dictionary to store results
    results = {}
    # Perform chi-square test for each column
    for column in filtered_data_bool.columns:
        if all(filtered_data_bool[column]):
            continue
        if column != cross_variable:
            chi2, p_value, cramer_v = chi_square_test(filtered_data_bool[cross_variable], filtered_data_bool[column], correction)
            results[column] = {'Chi-square': chi2, 'P-value': p_value, 'Cramer\'s V': cramer_v}

    # Create a DataFrame from the results
    results_df = pd.DataFrame.from_dict(results, orient='index')

    results_df = results_df.reset_index(names='code').merge(variables_scale_info, on='code')

    if not results_df.empty:
        return results_df[['text', 'Cramer\'s V', 'P-value', 'scale_type']].sort_values(by=['Cramer\'s V'], ascending=True)
    else:
        return pd.DataFrame()

def copy_axis_style(source_axis, invisible: bool):
    target_axis = copy(source_axis)
    target_axis.majorGridlines = copy_chart_lines(source_axis.majorGridlines, invisible)
    return target_axis

def copy_chart_lines(source_lines, invisible: bool):
    if invisible:
        return None
    else:
        target_lines = openpyxl.chart.line_chart.ChartLines()
        if source_lines:
            if source_lines.spPr is not None:
                target_lines.spPr = copy(source_lines.spPr)
        return target_lines

def copy_chart_style(source_chart, target_chart):
    target_chart.type = "bar"
    target_chart.legend = None

    for src_serie, tgt_serie in zip(source_chart.series, target_chart.series):
        tgt_serie.graphicalProperties = copy(src_serie.graphicalProperties)
        tgt_serie.tx = copy(src_serie.tx)
        tgt_serie.invertIfNegative = copy(src_serie.invertIfNegative)
        tgt_serie.dLbls = copy(src_serie.dLbls)

    # Copy axis styles
    target_chart.x_axis = copy_axis_style(source_chart.x_axis, invisible=True)
    target_chart.y_axis = copy_axis_style(source_chart.y_axis, invisible=False)

def create_chart(worksheet, source_chart, dataframe, chart_title, chart_destination):
    # If you have the data in a DataFrame
    data = Reference(worksheet, min_col=2, min_row=2, max_row=len(dataframe) + 1, max_col=2)
    categories = Reference(worksheet, min_col=1, min_row=2, max_row=len(dataframe) + 1)

    new_chart = BarChart()

    new_chart.add_data(data)
    new_chart.set_categories(categories)
    new_chart.title = chart_title

    # Set the size of the chart
    new_chart.width = 25  # set width to 25 units
    new_chart.height = 20  # set height to 20 units

    # Copy the style from source to target chart
    copy_chart_style(source_chart, new_chart)

    worksheet.add_chart(new_chart, chart_destination)

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

def set_time_zone_to_file(zip_file: io.BytesIO, file: str):
    info = zip_file.getinfo(os.path.basename(file))
    current_time = datetime.now(time_zone)
    info.date_time = (
        current_time.year,
        current_time.month,
        current_time.day,
        current_time.hour,
        current_time.minute,
        current_time.second
    )

def segment_spss(jobs: pd.DataFrame, spss_file: BytesIO):
    print('Started execution')
    temp_file_name = get_temp_file(spss_file)

    survey_data, metadata = pyreadstat.read_sav(
        temp_file_name,
        apply_value_formats=False
    )

    survey_data = survey_data.dropna(how='all')

    inverted_scales_keywords = get_inverted_scales_keywords()

    # Create a BytesIO object to store the zip file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:

        jobs_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        jobs.to_excel(jobs_temp_file.name, index=False)
        zip_file.write(f'{jobs_temp_file.name}', arcname='scenarios.xlsx')
        set_time_zone_to_file(zip_file, 'scenarios.xlsx')

        if jobs['cross_variable'].any():

            xlsx_temp_file = tempfile.NamedTemporaryFile(delete=False)

            # Create a new Excel file
            xlsx_file_name = f"chi2_{spss_file.name.split('.')[0].replace('Base ', '')}.xlsx"
            wb = openpyxl.Workbook()
            wb.remove(wb.active)

            # Read the existing Excel file
            existing_file = f"static/templates/chart_template.xlsx"
            wb_existing = openpyxl.load_workbook(existing_file)
            ws_existing = wb_existing.active

            # Find the chart in the existing worksheet
            source_chart = None
            for chart_obj in ws_existing._charts:
                if isinstance(chart_obj, BarChart):
                    source_chart = chart_obj
                    break

            if source_chart is None:
                print("Chart not found in the specified location.")
                exit()

        for _, job in jobs.iterrows():
            if job['variables']:
                if ',' in job['variables']:
                    variables = [variable.strip() for variable in job['variables'].split(',')]
                else:
                    variables = [variable.strip() for variable in job['variables'].split('\n')]
            else:
                variables = survey_data.columns.to_list()

            if job['condition']:
                try:
                    filtered_data = survey_data[variables].query(job['condition'])
                except SyntaxError as e:
                    raise e
            else:
                filtered_data = survey_data[variables]
            # Write filtered data to a temporary sav file
            sav_file_name = f"{spss_file.name.split('.')[0].replace('Base ', '')}_{job['scenario_name']}.sav"
            sav_temp_file = tempfile.NamedTemporaryFile(delete=False)
            pyreadstat.write_sav(
                filtered_data,
                sav_temp_file.name,
                column_labels={k: v for k, v in metadata.__dict__['column_names_to_labels'].items() if k in variables},
                variable_value_labels={k: v for k, v in metadata.__dict__['variable_value_labels'].items() if k in variables},
            )

            if job['cross_variable']:
                correction = False
                chi2_df = process_chi2(
                    sav_temp_file.name,
                    job['cross_variable'],
                    job['chi2_mode'],
                    inverted_scales_keywords,
                    correction,
                )

                # Create a new workbook object and select the active worksheet
                wb.create_sheet(job['scenario_name'])
                ws = wb[job['scenario_name']]

                # Write DataFrame content to the worksheet
                for r in dataframe_to_rows(chi2_df, index=False, header=True):
                    ws.append(r)

                # Create chart in the worksheet
                create_chart(ws, source_chart, chi2_df, 'Intención de compra', "E3")

            # Add the temporary sav file to the zip file with custom arcname
            zip_file.write(sav_temp_file.name, arcname=sav_file_name)
            set_time_zone_to_file(zip_file, sav_file_name)
            # Close and delete the temporary sav file
            sav_temp_file.close()
            os.unlink(sav_temp_file.name)

        if jobs['cross_variable'].any():
            # Save the new Excel file
            wb.save(xlsx_temp_file)
            wb.close()

            zip_file.write(f'{xlsx_temp_file.name}', arcname=xlsx_file_name)
            set_time_zone_to_file(zip_file, xlsx_file_name)
            xlsx_temp_file.close()
            os.unlink(xlsx_temp_file.name)

    # Close and reset the BytesIO buffer
    zip_buffer.seek(0)

    return zip_buffer
