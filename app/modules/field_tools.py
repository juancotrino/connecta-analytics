import itertools

import numpy as np
import pandas as pd

import streamlit as st

from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Border, Side, Font
from app.modules.utils import get_temp_file
from collections import Counter

from firebase_admin import firestore

from app.modules.utils import get_countries, write_temp_excel


COUNTRY_NAME_ALIASES = {"Brasil": "Brazil"}
COUNTRY_CODE_FALLBACKS = {
    "Costa Rica": "CR",
    "Colombia": "CO",
    "Ecuador": "EC",
    "Mexico": "MX",
    "Peru": "PE",
    "Brasil": "BR",
    "Chile": "CL",
    "Panama": "PA",
    "Guatemala": "GT",
    "Dominican Republic": "DO",
    "Nicaragua": "NI",
}


@st.cache_data(show_spinner=False)
def get_business_countries() -> dict[str, str]:
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()
    if not document.exists:
        return {}

    country_names = document.to_dict().get("countries", [])
    country_codes = get_countries()
    return {
        country_name: country_codes.get(
            country_name,
            country_codes.get(
                COUNTRY_NAME_ALIASES.get(country_name, ""),
                COUNTRY_CODE_FALLBACKS.get(country_name),
            ),
        )
        for country_name in country_names
        if country_codes.get(country_name)
        or country_codes.get(COUNTRY_NAME_ALIASES.get(country_name, ""))
        or COUNTRY_CODE_FALLBACKS.get(country_name)
    }


@st.cache_data(show_spinner=False)
def get_field_supervisors() -> list[dict]:
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()
    if document.exists:
        return document.to_dict().get("field_supervisors", [])
    return []


def save_field_supervisors(supervisors: list[dict]) -> None:
    db = firestore.client()
    db.collection("settings").document("business_data").update(
        {"field_supervisors": supervisors}
    )


def check_percentage_total(
    variables: dict[str, pd.DataFrame], variable_type: str = "independent"
):
    for variable, data in variables.items():
        match variable_type:
            case "independent":
                if data["percentage"].sum() != 100:
                    raise Exception(
                        f"Percentage sum for variable '{variable}' is not 100. "
                        f"Actual sum: {data['percentage'].sum()}."
                    )
            case "nested":
                higher_variable = variable.split("-")[0].strip()
                grouped_data = data.groupby(higher_variable).sum().reset_index()
                unique_values = data.iloc[:, 0].unique()

                for value in unique_values:
                    value_percentage_sum = grouped_data[
                        grouped_data[higher_variable] == value
                    ]["percentage"].to_list()[0]
                    if value_percentage_sum != 100:
                        raise Exception(
                            f"Percentage sum for nested variable '{variable}' "
                            f"for value '{value}' is not 100. "
                            f"Actual sum: {value_percentage_sum}."
                        )


def get_expanded_variable_pollsters(variable_pollsters_df: pd.DataFrame):
    # Step 1: Repeat rows based on the 'Number of Pollsters' column
    expanded_df = variable_pollsters_df.loc[
        variable_pollsters_df.index.repeat(
            variable_pollsters_df["Number of Pollsters"].astype(int)
        )
    ].reset_index(drop=True)

    # Step 2: Add a 'ID per Variable' column within each group (Values)
    expanded_df["ID per Variable"] = expanded_df.groupby("Values").cumcount() + 1

    return expanded_df


def get_expanded_surveys(
    total_surveys: int,
    total_pollsters: int,
    variable_pollsters: str | None,
    expanded_variable_pollsters: pd.DataFrame | None,
    variable_percentages_dict: dict,
    variable_nested_percentages_dict: dict,
    selected_variables_data: dict,
    selected_variables: list[str],
):
    if not total_surveys:
        raise Exception("Missing total number of surveys.")

    if not total_pollsters:
        raise Exception("Missing number of pollsters.")

    ordered_selected_variables_data = {
        variable: selected_variables_data[variable] for variable in selected_variables
    }

    combinations = list(itertools.product(*ordered_selected_variables_data.values()))

    combinations_df = pd.DataFrame(
        combinations, columns=ordered_selected_variables_data.keys()
    )

    for variable in variable_percentages_dict:
        combinations_df = pd.merge(
            combinations_df,
            variable_percentages_dict[variable],
            on=variable,
            how="left",
            suffixes=[f"_comb_{variable}", f"_{variable}"],
        )

    for variable in variable_nested_percentages_dict:
        combinations_df = pd.merge(
            combinations_df,
            variable_nested_percentages_dict[variable],
            on=[v.strip() for v in variable.split("-")],
            how="left",
            suffixes=[f"_independent_{variable}", f"_{variable}"],
        )
    percentage_columns = combinations_df.loc[
        :, combinations_df.columns.str.contains("percentage")
    ]
    combinations_df[percentage_columns.columns] = percentage_columns.astype(float)
    combinations_df.loc[:, combinations_df.columns.str.contains("percentage")] /= 100
    percentage_columns = combinations_df.loc[
        :, combinations_df.columns.str.contains("percentage")
    ]
    combinations_df["percentage"] = percentage_columns.prod(axis=1)
    combinations_df["surveys_float"] = combinations_df["percentage"] * total_surveys
    combinations_df["surveys"] = round(combinations_df["surveys_float"])

    # Calculate the difference between the total surveys and the sum of rounded surveys
    survey_diff = int(total_surveys - combinations_df["surveys"].sum())

    # Adjust the survey counts to match total_surveys
    if survey_diff != 0:
        # Find the rows with the smallest fractional part
        differences = (
            combinations_df["surveys_float"] - combinations_df["surveys"]
        ).abs()

        # Sort the rows based on the differences (to adjust the smallest fractional part)
        combinations_df["adjustment"] = differences
        combinations_df.sort_values("adjustment", ascending=False, inplace=True)

        # Adjust the rows to make the total sum match total_surveys
        for i in range(abs(survey_diff)):
            if survey_diff > 0:
                # Increment the survey count for the row with the smallest fractional part
                combinations_df.iloc[i, combinations_df.columns.get_loc("surveys")] += 1
            elif survey_diff < 0:
                # Decrement the survey count for the row with the smallest fractional part, but ensure it's not negative
                if (
                    combinations_df.iloc[i, combinations_df.columns.get_loc("surveys")]
                    > 0
                ):
                    combinations_df.iloc[
                        i, combinations_df.columns.get_loc("surveys")
                    ] -= 1

    # Ensure surveys are integers and non-negative
    combinations_df["surveys"] = combinations_df["surveys"].clip(lower=0).astype(int)

    # Ensure surveys are integers
    combinations_df["surveys"] = combinations_df["surveys"].astype(int)

    # Create the new DataFrame by repeating each row based on the 'surveys' column
    expanded_df = combinations_df[selected_variables].loc[
        np.repeat(combinations_df.index.values, combinations_df["surveys"])
    ]

    # Optionally, reset the index for the new DataFrame
    expanded_df = expanded_df.sort_values(selected_variables).reset_index(drop=True)

    if expanded_variable_pollsters is None:
        # Create an array of 16 elements (you can change these values as needed)
        pollsters = np.arange(1, total_pollsters + 1)  # Here I'm using numbers 1 to 16

        # Repeat the elements array until it covers the entire number of rows
        repeated_elements = np.tile(
            pollsters, int(np.ceil(len(expanded_df) / total_pollsters))
        )[: len(expanded_df)]

        # Add this array as a new column in your DataFrame
        expanded_df["Pollster"] = repeated_elements
    else:
        unique_values_variable_pollster = (
            expanded_variable_pollsters["Values"].unique().tolist()
        )
        expanded_df["Pollster"] = None
        for unique_value in unique_values_variable_pollster:
            filtered_expanded_df = expanded_df[
                expanded_df[variable_pollsters] == unique_value
            ].copy()
            pollsters_per_variable_value = expanded_variable_pollsters[
                expanded_variable_pollsters["Values"] == unique_value
            ]["ID per Variable"]
            repeated_elements = np.tile(
                pollsters_per_variable_value,
                int(
                    np.ceil(
                        len(filtered_expanded_df) / len(pollsters_per_variable_value)
                    )
                ),
            )[: len(filtered_expanded_df)]

            filtered_expanded_df["Pollster"] = repeated_elements
            filtered_expanded_df["Pollster"] = (
                filtered_expanded_df[variable_pollsters].astype(str)
                + "-"
                + filtered_expanded_df["Pollster"].astype(str)
            )

            expanded_df.update(filtered_expanded_df)

    # Ensure final length matches total_surveys
    if len(expanded_df) != total_surveys:
        # If there's a discrepancy, adjust the number of rows
        expanded_df = expanded_df.head(total_surveys)

    expanded_df = expanded_df.reset_index(names="ID")
    expanded_df["ID"] += 1

    return expanded_df



def check_base_xlsx(xlsx_file: BytesIO):
    temp_file_name_xlsx = get_temp_file(xlsx_file, ".xlsx")

    # Load the existing Excel file
    wb_existing = load_workbook(temp_file_name_xlsx)

    wb_new = Workbook()
    default_sheet = wb_new.active
    wb_new.remove(default_sheet)
    ws_base = wb_existing.worksheets[0]
    ws_check = wb_new.create_sheet(title="Check Base")

    redFill = PatternFill(start_color="C80000", end_color="C80000", fill_type="solid")

    yellowFill = PatternFill(
        start_color="FFFF00", end_color="FFFF00", fill_type="solid"
    )

    greenFillTitle = PatternFill(
        start_color="70AD47", end_color="70AD47", fill_type="solid"
    )

    medium_border = Border(
        left=Side(style="medium"),
        right=Side(style="medium"),
        top=Side(style="medium"),
        bottom=Side(style="medium"),
    )

    ws_check.cell(row=1, column=1).value = "Pregunta"
    ws_check.cell(row=1, column=2).value = "# de Registros Validos"
    ws_check.cell(row=1, column=3).value = "Ids Faltantes"
    ws_check.cell(row=1, column=4).value = "Respuestas"

    for col in range(1,5):
        ws_check.cell(row=1,column=col).fill=greenFillTitle
        ws_check.cell(row=1,column=col).font = Font(color = "FFFFFF")
        ws_check.cell(row=1,column=col).border = medium_border
        column_letter = get_column_letter(col)
        if col==1:
            width_col=30
        elif col in [2]:
            width_col=8
        elif col in [3]:
            width_col=50
        elif col in [4]:
            width_col=50
        else:
            width_col=7
        ws_check.column_dimensions[column_letter].width = width_col

    ws_check.auto_filter.ref = ws_check.dimensions

    total_rows = ws_base.max_row - 1
    current_out_row = 2

    col_idx = 2
    while col_idx <= ws_base.max_column:
        raw_name = ws_base.cell(row=1, column=col_idx).value
        raw_name_str = str(raw_name).strip() if raw_name is not None else ""

        # Extraer hasta las primeras 5 palabras (si tiene menos, toma las que haya)
        words = raw_name_str.split()
        question_code = " ".join(words[:5]) if words else ""

        # --- 1. EVALUACIÓN DE PRIMERA COLUMNA ---
        first_col_vals = set()
        for r_idx in range(2, ws_base.max_row + 1):
            val = ws_base.cell(row=r_idx, column=col_idx).value
            if val is not None and str(val).strip() != "":
                first_col_vals.add(str(val).strip())

        # Contador de columnas dentro del grupo que tienen más de 1 valor distinto (ej. "Otro cuál")
        multi_val_cols_count = 1 if len(first_col_vals) > 1 else 0

        end_col_idx = col_idx

        # --- 2. EXPANSIÓN DINÁMICA BIDIRECCIONAL DEL GRUPO ---
        start_col_idx = col_idx
        end_col_idx = col_idx

        if question_code != "":
            # A) Buscar hacia ATRÁS mientras compartan el mismo código de pregunta
            while start_col_idx - 1 >= 2:
                prev_raw_name = ws_base.cell(row=1, column=start_col_idx - 1).value
                prev_raw_name_str = str(prev_raw_name).strip() if prev_raw_name is not None else ""
                prev_words = prev_raw_name_str.split()
                prev_code = " ".join(prev_words[:5]) if prev_words else ""

                if prev_code == question_code:
                    start_col_idx -= 1
                else:
                    break

            # B) Buscar hacia ADELANTE mientras compartan el mismo código de pregunta
            while end_col_idx + 1 <= ws_base.max_column:
                next_raw_name = ws_base.cell(row=1, column=end_col_idx + 1).value
                next_raw_name_str = str(next_raw_name).strip() if next_raw_name is not None else ""
                next_words = next_raw_name_str.split()
                next_code = " ".join(next_words[:5]) if next_words else ""

                if next_code == question_code:
                    end_col_idx += 1
                else:
                    break

            # C) EVALUAR LÍMITE DE COLUMNAS MULTIVALOR DENTRO DEL BLOQUE COMPLETO ENCONTRADO
            # Contamos cuántas columnas en el rango [start_col_idx, end_col_idx] tienen > 1 valor
            multi_val_cols_count = 0
            for g_col in range(start_col_idx, end_col_idx + 1):
                col_vals = set()
                for r_idx in range(2, ws_base.max_row + 1):
                    val = ws_base.cell(row=r_idx, column=g_col).value
                    if val is not None and str(val).strip() != "":
                        col_vals.add(str(val).strip())
                        if len(col_vals) > 1:
                            multi_val_cols_count += 1
                            break

            # Si el bloque completo superó el límite de 1 columna abierta/multivalor (ej. es una Rejilla),
            # deshacemos la agrupación y procesamos la columna actual como individual.
            if multi_val_cols_count > 1:
                start_col_idx = col_idx
                end_col_idx = col_idx

        start_letter = get_column_letter(col_idx)

        missing_ids = []
        valid_count = 0
        values_list = []  # Lista para acumular los valores encontrados

        # --- CASO 1: Columna Individual (Sin coincidencia de nombre o 1ra columna con múltiples valores) ---
        if col_idx == end_col_idx:
            col_name = f"({start_letter}) {raw_name_str}"

            for row_idx in range(2, ws_base.max_row + 1):
                cell_val = ws_base.cell(row=row_idx, column=col_idx).value
                is_empty = cell_val is None or str(cell_val).strip() == ""

                if is_empty:
                    id_val = ws_base.cell(row=row_idx, column=1).value
                    missing_ids.append(str(id_val) if id_val is not None else "")
                else:
                    valid_count += 1
                    values_list.append(str(cell_val).strip())

            next_col_idx = col_idx + 1

        # --- CASO 2: Recorrido por Grupo Ajustado (Hasta donde todas fueron válidas) ---
        else:
            end_letter = get_column_letter(end_col_idx)
            col_name = f"({start_letter}-{end_letter}) {raw_name_str}"

            for row_idx in range(2, ws_base.max_row + 1):
                row_has_value = False

                # Revisa si al menos una celda del grupo recortado tiene valor
                for g_col in range(col_idx, end_col_idx + 1):
                    cell_val = ws_base.cell(row=row_idx, column=g_col).value
                    if cell_val is not None and str(cell_val).strip() != "":
                        row_has_value = True
                        values_list.append(str(cell_val).strip())

                if row_has_value:
                    valid_count += 1
                else:
                    id_val = ws_base.cell(row=row_idx, column=1).value
                    missing_ids.append(str(id_val) if id_val is not None else "")

            next_col_idx = end_col_idx + 1

        # --- ESCRITURA DE RESULTADOS ---
        ws_check.cell(row=current_out_row, column=1, value=col_name)

        cell_valid = ws_check.cell(row=current_out_row, column=2, value=valid_count)

        if valid_count == 0:
            cell_valid.fill = redFill
        elif valid_count < total_rows:
            cell_valid.fill = yellowFill

        ids_str = ", ".join(missing_ids) if missing_ids else ""
        if valid_count != 0:
            ws_check.cell(row=current_out_row, column=3, value=ids_str)

        val_counts = Counter(values_list)
        counts_str = ", ".join([f"{val}: ({count})" for val, count in val_counts.most_common()])
        ws_check.cell(row=current_out_row, column=4, value=counts_str)

        ws_check.cell(row=current_out_row, column=5, value=" ")

        current_out_row += 1

        # El puntero avanza a la columna siguiente a la última agrupada con éxito
        col_idx = next_col_idx

    ws_check.auto_filter.ref = ws_check.dimensions

    # ==============================================================================
    # --- BLOQUE FINAL: GENERACIÓN DE TABLAS DE RESUMEN AL INICIO DEL LIBRO ---
    # ==============================================================================

    # Crear la nueva pestaña EN LA PRIMERA POSICIÓN (index=0)
    ws_summary = wb_new.create_sheet(title="Resumen Faltantes", index=0)

    # Definir encabezados para las dos tablas
    headers = ["Variable / Pregunta", "Válidos", "IDs Faltantes", "Conteo de Respuestas"]

    # 1. Escribir Encabezado Tabla Amarillos (Incompletos) -> Columnas A a D
    for col_num, h_text in enumerate(headers, 1):
        cell = ws_summary.cell(row=1, column=col_num, value=f"[INCOMPLETOS] {h_text}")
        cell.fill = yellowFill

    # 2. Escribir Encabezado Tabla Rojos (Vacíos) -> Columnas F a I (deja la E libre)
    for col_num, h_text in enumerate(headers[:2], 6):
        cell = ws_summary.cell(row=1, column=col_num, value=f"[EN CERO] {h_text}")
        cell.fill = redFill

    # Contadores de filas para cada tabla
    out_row_yellow = 2
    out_row_red = 2

    # Recorrer la tabla de la hoja ws_check ya generada
    for r_idx in range(2, current_out_row):
        col_name = ws_check.cell(row=r_idx, column=1).value
        val_count = ws_check.cell(row=r_idx, column=2).value
        ids_faltantes = ws_check.cell(row=r_idx, column=3).value
        conteo_resp = ws_check.cell(row=r_idx, column=4).value

        # Si la celda es None (por seguridad), la convertimos a 0
        val_count_num = val_count if isinstance(val_count, int) else 0

        # CASO ROJO: Cero registros válidos
        if val_count_num == 0:
            ws_summary.cell(row=out_row_red, column=6, value=col_name)
            c_val = ws_summary.cell(row=out_row_red, column=7, value=val_count_num)
            c_val.fill = redFill
            ws_summary.cell(row=out_row_red, column=8, value=ids_faltantes)

            out_row_red += 1

        # CASO AMARILLO: Registros incompletos (entre 1 y total_rows - 1)
        elif val_count_num < total_rows:
            ws_summary.cell(row=out_row_yellow, column=1, value=col_name)
            c_val = ws_summary.cell(row=out_row_yellow, column=2, value=val_count_num)
            c_val.fill = yellowFill
            ws_summary.cell(row=out_row_yellow, column=3, value=ids_faltantes)
            ws_summary.cell(row=out_row_yellow, column=4, value=conteo_resp)
            out_row_yellow += 1

    # ==============================================================================
    # --- CONFIGURACIÓN DE ANCHOS DE COLUMNA (column_dimensions) ---
    # ==============================================================================

    # Tabla Amarillos (A-D)
    ws_summary.column_dimensions['A'].width = 30
    ws_summary.column_dimensions['B'].width = 8
    ws_summary.column_dimensions['C'].width = 10
    ws_summary.column_dimensions['D'].width = 10

    # Columna espacio de separación (E)
    ws_summary.column_dimensions['E'].width = 3

    # Tabla Rojos (F-I)
    ws_summary.column_dimensions['F'].width = 30
    ws_summary.column_dimensions['G'].width = 8
    ws_summary.column_dimensions['H'].width = 10
    ws_summary.column_dimensions['I'].width = 10

    # Ajustar filtros automáticos en la hoja de resumen
    ws_summary.auto_filter.ref = ws_summary.dimensions

    return write_temp_excel(wb_new)
