import warnings
from io import BytesIO
import tempfile
import string

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportions_ztest

from openpyxl import Workbook, load_workbook
from openpyxl.cell.text import InlineFont
from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import PatternFill, Border, Side, Alignment, Protection, Font

import streamlit as st

letters_list = list(string.ascii_uppercase)

def extract_digits(cell):
    cell = str(cell)
    match = pd.Series(cell).str.extract('(\d+)')[0][0]
    return int(match) if pd.notna(match) else None

def group_consecutive_indexes(index_list):
    if not index_list:
        return []

    sorted_indexes = sorted(set(index_list))
    groups = []
    group = [sorted_indexes[0]]

    for i in range(1, len(sorted_indexes)):
        if sorted_indexes[i] == sorted_indexes[i - 1] + 1:
            group.append(sorted_indexes[i])
        else:
            groups.append(group)
            group = [sorted_indexes[i]]

    groups.append(group)
    return groups

def calculate_percentages(inner_df: pd.DataFrame, total_df: pd.DataFrame, total_index: int) -> pd.DataFrame:
    percentage_inner_df = inner_df.copy()
    for column in inner_df.columns:
        percentage_inner_df[column] = (inner_df[column] / total_df.loc[total_index, column]) * 100
    return percentage_inner_df

def calculate_differences(x1: int, x2: int, n1: int, n2: int, sigma: float = 0.05) -> bool:
    if n1 < 30 or n2 < 30 or x1 == 0 or x2 == 0 or n1 == 0 or n2 == 0:
        return False

    # Número de éxitos y tamaño de muestra en cada grupo
    counts = np.array([x1, x2])
    nobs = np.array([n1, n2])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        # Prueba z de dos proporciones
        _, p_value = proportions_ztest(counts, nobs)

    # print(stat, p_value, x1, x2, n1, n2)

    return p_value < sigma

def significant_differences(
    inner_df: pd.DataFrame,
    data: pd.DataFrame,
    total_index: int,
    letters_inner_dict: dict[str, str]
) -> pd.DataFrame:

    columns = inner_df.columns
    n_cols = len(columns)

    inner_differences_df = pd.DataFrame('', index=inner_df.index, columns=inner_df.columns)

    for i in range(n_cols):
        for j in range(i + 1, n_cols):
            col1 = columns[i]
            col2 = columns[j]

            for index in inner_df.index:
                x1 = inner_df.at[index, col1]
                x2 = inner_df.at[index, col2]
                n1 = data.loc[total_index, col1]
                n2 = data.loc[total_index, col2]

                if calculate_differences(x1, x2, n1, n2):
                    if (x1 / n1) > (x2 / n2):
                        if inner_differences_df.at[index, col1]:
                            inner_differences_df.at[index, col1] += f',{letters_inner_dict[col2]}'
                        else:
                            inner_differences_df.at[index, col1] = letters_inner_dict[col2]
                    else:
                        if inner_differences_df.at[index, col2]:
                            inner_differences_df.at[index, col2] += f',{letters_inner_dict[col1]}'
                        else:
                            inner_differences_df.at[index, col2] = letters_inner_dict[col1]

    return inner_differences_df

def combine_values(num: int | float, string: str, decimals: int=2):
    if pd.isna(num) and pd.isna(string):
        return np.nan
    elif pd.isna(num):
        return string.strip()
    elif pd.isna(string):
        if isinstance(num, float):
            return f"{num:.{decimals}f}".strip()
        else:
            return str(num).strip()
    else:
        if isinstance(num, float):
            num = f"{num:.{decimals}f}"
        return f"{num} {string}".strip()

# Función para combinar los dataframes
def combine_dataframes(df1, df2, decimals=2):
    combined_df = pd.DataFrame()

    for col in df1.columns:
        combined_df[col] = [combine_values(num, string, decimals) for num, string in zip(df1[col], df2[col])]

    return combined_df

# Function to copy cell styles
def copy_styles(cell_source, cell_target):
    if cell_source.has_style:
        cell_target.font = Font(
            name=cell_source.font.name,
            size=cell_source.font.size,
            bold=cell_source.font.bold,
            italic=cell_source.font.italic,
            vertAlign=cell_source.font.vertAlign,
            underline=cell_source.font.underline,
            strike=cell_source.font.strike,
            color=cell_source.font.color
        )

        cell_target.border = Border(
            left=Side(
                border_style=cell_source.border.left.style,
                color=cell_source.border.left.color
            ),
            right=Side(
                border_style=cell_source.border.right.style,
                color=cell_source.border.right.color
            ),
            top=Side(
                border_style=cell_source.border.top.style,
                color=cell_source.border.top.color
            ),
            bottom=Side(
                border_style=cell_source.border.bottom.style,
                color=cell_source.border.bottom.color
            )
        )

        cell_target.fill = PatternFill(
            fill_type=cell_source.fill.fill_type,
            start_color=cell_source.fill.start_color,
            end_color=cell_source.fill.end_color
        )

        cell_target.number_format = cell_source.number_format
        cell_target.protection = Protection(
            locked=cell_source.protection.locked,
            hidden=cell_source.protection.hidden
        )
        cell_target.alignment = Alignment(
            horizontal=cell_source.alignment.horizontal,
            vertical=cell_source.alignment.vertical,
            text_rotation=cell_source.alignment.text_rotation,
            wrap_text=cell_source.alignment.wrap_text,
            shrink_to_fit=cell_source.alignment.shrink_to_fit,
            indent=cell_source.alignment.indent
        )

def delete_col_with_merged_ranges(sheet, idx):
    sheet.delete_cols(idx)

    for mcr in sheet.merged_cells:
        if idx < mcr.min_col:
            mcr.shift(col_shift=-1)
        elif idx < mcr.max_col:
            mcr.shrink(right=1)

# Function to apply red color to the letter in the cell
def apply_red_color_to_letter(cell):
    value = cell.value
    if isinstance(value, str) and any(char.isalpha() for char in value):
        # Separate number and letter
        num = ''.join([char for char in value if char.isdigit()])
        letter = ','.join([char for char in value if char.isalpha()])

        # Apply formatting

        red = InlineFont(color='00FF0000')
        rich_text_cell = CellRichText()
        rich_text_cell.append(f'{num} ')
        rich_text_cell.append(TextBlock(red, letter))
        cell.value = rich_text_cell

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

# @st.cache_data(show_spinner=False)
def processing(xlsx_file: BytesIO):

    temp_file_name_xlsx = get_temp_file(xlsx_file)

    # Load the existing Excel file
    wb_existing = load_workbook(temp_file_name_xlsx)

    # List all sheet names
    sheet_names = wb_existing.sheetnames

    # Create a new Workbook
    wb_new = Workbook()

    # Remove the default sheet created with the new workbook
    default_sheet = wb_new.active
    wb_new.remove(default_sheet)

    # Iterate over all sheets
    for sheet_name in sheet_names:
        ws_existing = wb_existing[sheet_name]

        data = pd.read_excel(temp_file_name_xlsx, sheet_name=sheet_name)
        data['Unnamed: 2'] = (
            pd.to_numeric(data['Unnamed: 2'], errors='coerce')
            .fillna(data['Unnamed: 2'])
            .fillna('')
        )
        data_differences = data.copy()

        value_type = data['Unnamed: 2'].apply(lambda x: type(x))
        float_types = value_type[value_type == float]

        question_groups = group_consecutive_indexes(list(float_types.index))

        partial_df = data[data.index.isin([question_groups[0][0] - 1] + question_groups[0])]
        initial_category_group = partial_df.loc[partial_df.index[0], 'TOTAL'] # (A)
        category_groups_columns = partial_df.loc[partial_df.index[0], :].to_frame().reset_index()

        initial_category_indexes = group_consecutive_indexes(
            list(category_groups_columns[category_groups_columns[1] == initial_category_group][1:].index)
        )

        category_indexes = (
            [(initial_category_indexes[i][0], initial_category_indexes[i + 1][0] - 1) for i in range(len(initial_category_indexes) - 1)] +
            [(initial_category_indexes[-1][0], len(category_groups_columns) - 1)]
        )
        total_differeces_df = pd.DataFrame(index=range(len(data_differences)), columns=data_differences.columns)

        for question_group in question_groups:
            df_total_search = data_differences.loc[question_group[-1]:question_group[-1] + 6, :]
            total_index = df_total_search[df_total_search['Unnamed: 2'].str.contains('Total', na=False)].index[0]
            data_differences.loc[total_index, 'TOTAL'] = int(data_differences.loc[total_index, 'TOTAL'])

            data_differences.update(
                calculate_percentages(
                    data_differences[['TOTAL']].loc[question_group, :].astype(int),
                    data_differences,
                    total_index
                )
            )

            for category_group in category_indexes:
                columns_category_groups = category_groups_columns.loc[category_group[0]:category_group[1]]['index'].to_list()

                inner_df = data.loc[question_group, columns_category_groups].map(extract_digits)

                data_differences.update(inner_df)

                data_differences.loc[total_index, inner_df.columns] = data_differences.loc[total_index, inner_df.columns].infer_objects(copy=False).fillna(0).astype(int)

                data_differences.update(calculate_percentages(inner_df, data_differences, total_index))

                letters_inner_dict = {column: letter for column, letter in zip(inner_df.columns, letters_list[:len(inner_df.columns)])}

                inner_differences_df = significant_differences(inner_df, data_differences, total_index, letters_inner_dict)

                total_differeces_df.update(inner_differences_df)

        combined_differences_df = combine_dataframes(data_differences, total_differeces_df, 0)
        combined_differences_df['Unnamed: 2'] = np.where(
            combined_differences_df['Unnamed: 2'] == '1',
            combined_differences_df['Unnamed: 1'],
            combined_differences_df['Unnamed: 2']
        )

        combined_differences_df['Unnamed: 2'] = combined_differences_df['Unnamed: 2'].replace('', np.nan)
        first_all_nan_index = combined_differences_df[combined_differences_df.isna().all(axis=1)].index[0]

        ws_new = wb_new.create_sheet(title=sheet_name)

        # Copy styles and merged cells from existing sheet to new sheet
        for row in ws_existing.iter_rows():
            for cell in row:
                new_cell = ws_new.cell(row=cell.row, column=cell.column, value=cell.value)
                copy_styles(cell, new_cell)

        # Copy column widths
        for col in ws_existing.columns:
            column_letter = col[first_all_nan_index + 1].column_letter
            ws_new.column_dimensions[column_letter].width = ws_existing.column_dimensions[column_letter].width

        # Write DataFrame to the new worksheet, starting after the existing data
        start_row = 1
        start_column = 1
        for r_idx, row in enumerate(dataframe_to_rows(combined_differences_df, index=False, header=True), start=start_row):
            for c_idx, value in enumerate(row, start=start_column):
                new_cell = ws_new.cell(row=r_idx, column=c_idx, value=value)

        # Copy merged cell ranges
        for merged_cell in ws_existing.merged_cells.ranges:
            ws_new.merge_cells(str(merged_cell))

        # Iterate through merged cell ranges and unmerge those in column B
        for merged_range in list(ws_new.merged_cells.ranges):
            min_col, min_row, max_col, max_row = range_boundaries(merged_range.coord)

            if min_col == 2 and max_col == 2:  # Check if the merged range is in column B
                ws_new.unmerge_cells(start_row=min_row, start_column=min_col, end_row=max_row, end_column=max_col)

        # Apply bold formatting to the first two columns
        for row in ws_new.iter_rows():
            for cell in row[:3]:  # First two columns
                cell.font = Font(bold=True)

        # Delete column B
        delete_col_with_merged_ranges(ws_new, 2)

        # Loop through each range and apply the formatting
        for question_group in question_groups:
            for row in question_group:
                for category_group in category_indexes:
                    col_start, col_end = category_group
                    for col in range(col_start, col_end + 1):
                        cell = ws_new.cell(row=row + 2, column=col)
                        apply_red_color_to_letter(cell)

        ws_new.cell(row=1, column=1).value = ''

        ws_new.column_dimensions["A"].width = 400 / 8.43
        ws_new.column_dimensions["B"].width = 150 / 8.43

        # Set fixed column width for all columns
        fixed_column_width = 80 / 8.43
        for col in range(3, ws_new.max_column + 1):
            column_letter = get_column_letter(col)
            ws_new.column_dimensions[column_letter].width = fixed_column_width


        # Set fixed row height for all rows
        fixed_row_height = 20 / 1.33
        for row in range(1, ws_new.max_row + 1):
            ws_new.row_dimensions[row].height = fixed_row_height

    return write_temp_excel(wb_new)
