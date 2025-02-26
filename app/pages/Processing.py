import pandas as pd

import streamlit as st

from app.modules.preprocessing import preprocessing, generate_open_ended_db
from app.modules.processing import processing
from app.modules.database_transformation import transform_database
from app.modules.processor import (
    getPreProcessCode,
    getPreProcessCode2,
    checkPreProcessCodeUnique,
    getVarsForPlantilla,
    getProcessCode2,
    getSegmentCode,
    getPenaltysCode2,
    getCruces2,
    getPenaltysCode,
    getCruces,
)
from app.modules.utils import try_download, get_temp_file, write_temp_sav


def main():
    # -------------- SETTINGS --------------
    st.markdown("""
    This tool calculates significant significance and penalties and formats the processing tables from SPSS in an `.xlsx` format.
    """)

    st.header("Processing")

    with st.container(border=True):
        st.markdown("### Preprocessing")

        with st.form("preprocessing_form"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Code Book")
                uploaded_file_preprocess_xlsx = st.file_uploader(
                    "Upload `.xlsx` file",
                    type=["xlsx", "xlsm"],
                    key="preprocessing_xlsx",
                )

            with col2:
                st.markdown("#### Database")
                uploaded_file_preprocess_sav = st.file_uploader(
                    "Upload `.sav` file", type=["sav"], key="preprocessing_sav"
                )

            preprocess_button = st.form_submit_button("Preprocess database")

            if (
                uploaded_file_preprocess_xlsx
                and uploaded_file_preprocess_sav
                and preprocess_button
            ):
                with st.spinner("Preprocessing..."):
                    # with st.status("Preprocessing...", expanded=True) as status:
                    temp_file_name_xlsx = get_temp_file(
                        uploaded_file_preprocess_xlsx, ".xlsx"
                    )
                    temp_file_name_sav = get_temp_file(uploaded_file_preprocess_sav)
                    try:
                        # if 'results' not in st.session_state:
                        results = preprocessing(temp_file_name_xlsx, temp_file_name_sav)
                        #     st.session_state['results'] = results
                        # results = st.session_state['results']

                        final_df, metadata = generate_open_ended_db(
                            results, temp_file_name_sav
                        )

                        final_db = write_temp_sav(final_df, metadata)
                        st.success("Database preprocessed successfully.")

                        logs_df = pd.DataFrame.from_dict(
                            results,
                            orient="index",
                            columns=["status_code", "elapsed_time", "usage", "retries"],
                        )

                        st.dataframe(logs_df)

                    except Exception as e:
                        st.error(e)

                    # status.update(
                    #     label="Preprocessing complete", state="complete", expanded=False
                    # )

        try:
            try_download(
                "Download processed database", final_db, "db_preprocessed", "sav"
            )
        except Exception:
            pass

        st.markdown("### SPSS Tables")

        with st.form("processing_form"):
            uploaded_file_process_xlsx = st.file_uploader(
                "Upload `.xlsx` file", type=["xlsx"], key="processing_xlsx"
            )
            uploaded_file_process_sav = st.file_uploader(
                "Upload `.sav` file", type=["sav"], key="processing_sav"
            )

            ruta = st.text_input("Output Pretabla File Path xlsx:")

            # checkinclude = st.checkbox("Include All")
            checkinclude = False

            process_button = st.form_submit_button("Get code to process")

            if (
                process_button
                and uploaded_file_process_xlsx
                and uploaded_file_process_sav
            ) or (uploaded_file_process_xlsx and uploaded_file_process_sav):
                with st.spinner("Processing Code SPSS..."):
                    name_ruta = "*" + ruta + ".\n"
                col1, col2 = st.columns(2)
                with col1:
                    col1.markdown("Preprocess code:")
                    with col1.container(height=250):
                        st.code(
                            getPreProcessCode(
                                uploaded_file_process_sav, uploaded_file_process_xlsx
                            ),
                            line_numbers=True,
                        )
                    warning = ""
                    if checkPreProcessCodeUnique(
                        uploaded_file_process_sav, uploaded_file_process_xlsx
                    )[0]:
                        if warning == "":
                            warning += "Run PreProcess Code only one time"
                        warning += " --- Code with Inverse code"
                    if checkPreProcessCodeUnique(
                        uploaded_file_process_sav, uploaded_file_process_xlsx
                    )[1]:
                        if warning == "":
                            warning += "Run PreProcess Code only one time"
                        warning += " --- Code with Custom Scales code"
                    if warning != "":
                        st.warning(warning)
                with col2:
                    col2.markdown("Code to segment base by references:")
                    with col2.container(height=250):
                        st.code(
                            getSegmentCode(
                                uploaded_file_process_sav, uploaded_file_process_xlsx
                            ),
                            line_numbers=True,
                        )
                st.markdown("### Code SPSS")
                col1, col2, col3 = st.columns(3)
                with col1:
                    col1.markdown("Code to gen Tables in SPSS:")
                    warning = ""
                    with col1.container(height=250):
                        code_button = st.form_submit_button("Get code SPSS to process")
                        if code_button:
                            warning = ""
                            with st.spinner("Processing Code SPSS..."):
                                process_code, warning = getProcessCode2(
                                    uploaded_file_process_sav,
                                    uploaded_file_process_xlsx,
                                    checkinclude,
                                    rutaarchivo=ruta,
                                )
                                st.code(
                                    name_ruta
                                    + getPreProcessCode(
                                        uploaded_file_process_sav,
                                        uploaded_file_process_xlsx,
                                    )
                                    + "\n"
                                    + getSegmentCode(
                                        uploaded_file_process_sav,
                                        uploaded_file_process_xlsx,
                                    )
                                    + "\nDATASET ACTIVATE ConjuntoDatos1.\n"
                                    + process_code,
                                    line_numbers=True,
                                )
                    if warning != "":
                        st.warning(warning)
                with col2:
                    col2.markdown("Code to gen Penaltys Tables in SPSS:")
                    with col2.container(height=250):
                        penaltys_button = st.form_submit_button(
                            "Get Penaltys code SPSS to process"
                        )
                        if penaltys_button:
                            warning = ""
                            with st.spinner("Penaltys Code SPSS..."):
                                if getPenaltysCode(uploaded_file_process_xlsx) != "":
                                    st.code(
                                        name_ruta
                                        + getPreProcessCode(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                        )
                                        + "\n"
                                        + getSegmentCode(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                        )
                                        + "\nDATASET ACTIVATE ConjuntoDatos1.\n"
                                        + getPenaltysCode2(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                            rutaarchivo=ruta,
                                        ),
                                        line_numbers=True,
                                    )
                                else:
                                    st.code("No Penaltys", line_numbers=True)

                with col3:
                    col3.markdown("Code to gen Cruces Tables in SPSS:")
                    with col3.container(height=250):
                        cruces_button = st.form_submit_button(
                            "Get Cruces code SPSS to process"
                        )
                        if cruces_button:
                            warning = ""
                            with st.spinner("Cruces Code SPSS..."):
                                if (
                                    getCruces(
                                        uploaded_file_process_sav,
                                        uploaded_file_process_xlsx,
                                        checkinclude,
                                    )
                                    != ""
                                ):
                                    st.code(
                                        name_ruta
                                        + getPreProcessCode(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                        )
                                        + "\n"
                                        + getSegmentCode(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                        )
                                        + "\nDATASET ACTIVATE ConjuntoDatos1.\n"
                                        + getCruces2(
                                            uploaded_file_process_sav,
                                            uploaded_file_process_xlsx,
                                            checkinclude,
                                            rutaarchivo=ruta,
                                        ),
                                        line_numbers=True,
                                    )
                                else:
                                    st.code("No Cruces", line_numbers=True)
            elif process_button and uploaded_file_process_sav:
                col1, col2 = st.columns(2)
                with col1:
                    col1.markdown("Preprocess code:")
                    with col1.container(height=250):
                        st.code(
                            getPreProcessCode2(uploaded_file_process_sav),
                            line_numbers=True,
                        )
                with col2:
                    col2.markdown("Text for Plantilla:")
                    with col2.container(height=250):
                        st.code(
                            getVarsForPlantilla(uploaded_file_process_sav)[0],
                            line_numbers=True,
                        )
                        results_plantilla = getVarsForPlantilla(
                            uploaded_file_process_sav
                        )[1]
        try:
            try_download(
                "Download Stadistics Plantilla",
                results_plantilla,
                "stadistics_plantilla",
                "xlsx",
            )
        except Exception:
            pass

        st.markdown("### Statistical Significance | Penalties")

        with st.form("statistical_processing_form"):
            st.write("Load excel file with the processing tables from SPSS.")

            # Add section to upload a file
            uploaded_file_xlsx = st.file_uploader(
                "Upload `.xlsx` file", type=["xlsx"], key="statistical_processing_xlsx"
            )

            process = st.form_submit_button("Process file")

            if uploaded_file_xlsx and process:
                with st.spinner("Processing..."):
                    results = processing(uploaded_file_xlsx)
                    st.success("Tables processed successfully.")

        try:
            try_download(
                "Download processed tables", results, "processed_tables", "xlsx"
            )
        except Exception:
            pass

    st.markdown("### Transform Database")

    with st.form("transform_database_form"):
        st.markdown("#### Database")

        st.write("Load `.sav` database file to be formatted.")

        # Add section to upload a file
        uploaded_file_sav = st.file_uploader(
            "Upload `.sav` file", type=["sav"], key="transform_database_sav"
        )

        config = {
            "visit_name": st.column_config.TextColumn(
                "Visit Name", width="small", required=True
            ),
        }

        st.markdown("#### Visits names")

        visit_names = st.data_editor(
            pd.DataFrame(columns=[k for k in config.keys()]),
            num_rows="dynamic",
            width=400,
            key="visit_names_df",
            column_config=config,
        )

        visit_names_list = visit_names["visit_name"].to_list()

        process = st.form_submit_button("Preprocess database")

        if uploaded_file_sav and process:
            with st.spinner("Processing..."):
                try:
                    preprocessing_results = transform_database(
                        uploaded_file_sav, visit_names_list
                    )
                    st.success("Database transformed successfully.")
                except Exception as e:
                    st.error(e)
    try:
        try_download(
            "Download processed database",
            preprocessing_results,
            "processed_database",
            "sav",
        )
    except Exception:
        pass
