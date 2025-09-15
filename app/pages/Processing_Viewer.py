import ast

import pandas as pd

import streamlit as st

from app.modules.processing_viewer import (
    get_categories,
    get_subcategories,
    get_question_groups,
    get_questions,
    get_study_countries,
    get_studies_names,
    download_studies_data,
    combine_metadata,
    combine_dictionaries,
    filter_df,
    get_cross_questions,
    build_statistical_significance_df,
    create_html_table,
    remap_references,
)
from app.modules.processing import get_references
from app.modules.utils import (
    _to_show,
    read_sav_db,
    read_sav_metadata,
    load_json,
    get_countries,
    get_companies_blobs,
)


def main():
    # -------------- SETTINGS --------------
    st.markdown("""
        This tool allows you to cross and get statistical significance for different variables of a study.
    """)

    company = st.session_state["company"]
    if not company:
        st.warning(
            "Your user is not associated with a company or client registered. "
            "Please contact the service administrator."
        )
        return

    companies_blobs = get_companies_blobs("connecta-app-1-service-processing")

    if company == "Connecta":
        ...
    elif company not in companies_blobs:
        st.warning(
            "We don't have records of any study for your company. "
            "Please contact the service administrator."
        )
        return

    st.markdown("### Study")

    categories = get_categories()
    product_category = st.selectbox(
        "Product category", categories, index=None, format_func=_to_show
    )

    if not product_category:
        return

    subcategories = get_subcategories(product_category)
    product_subcategory = st.selectbox(
        "Product subcategory", subcategories, index=None, format_func=_to_show
    )

    if not product_subcategory:
        return

    countries = get_study_countries(product_category, product_subcategory)
    selected_country = st.selectbox("Country", countries, index=None)

    if not selected_country:
        return

    countries_iso_2_code = get_countries()
    selected_country_code = countries_iso_2_code[selected_country]

    if company == "Connecta":
        company = st.selectbox("Company", companies_blobs)

    study_names = get_studies_names(
        product_category, product_subcategory, selected_country_code, company
    )

    selected_studies = st.multiselect("Studies", study_names)

    if not selected_studies:
        return

    studies_data = download_studies_data(
        product_category,
        product_subcategory,
        selected_country_code,
        company,
        selected_studies,
    )

    current_references = get_references(product_category, product_subcategory, company)

    with st.expander("Inspect variables"):
        sav_cols = st.columns(len(studies_data))
        studies_dbs = []
        studies_metadata = []
        studies_configs = []
        for col, (study, data) in zip(sav_cols, studies_data.items()):
            col.markdown(f"### {study}")
            sav_db = read_sav_db(data["sav"])
            metadata_df = read_sav_metadata(data["sav"])
            sav_db, metadata_df = remap_references(
                study, sav_db, metadata_df, current_references
            )
            studies_dbs.append(sav_db)
            studies_configs.append(load_json(data["json"])["config"])
            metadata_df["answer_options_count"] = (
                metadata_df["values"]
                .apply(lambda x: len(ast.literal_eval(x)) if x else 0)
                .astype(int)
            )
            col.dataframe(metadata_df, use_container_width=True)
            studies_metadata.append(metadata_df)

        db = pd.concat(studies_dbs).reset_index(drop=True)

        st.markdown("### Combined Database")
        st.dataframe(db)

    st.markdown("### Database filter")

    config = combine_dictionaries(studies_configs)
    metadata_df = combine_metadata(studies_metadata)

    fields = st.columns(len(config["filters"]))

    db = filter_df(fields, config["filters"], metadata_df, db)

    if db.empty:
        st.warning("The filters you applied to the database, return no records.")
        return

    st.markdown("### Statistical significance")

    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        question_groups = st.multiselect(
            "Question group", get_question_groups(product_category, product_subcategory)
        )

        questions_by_group = get_questions(
            product_category, product_subcategory, question_groups
        )

        # Flatten the questions list for the multiselect
        all_questions = [
            f"{group} | {q['label']}"
            for group, questions in questions_by_group.items()
            for q in questions
        ]

    with col2:
        selected_questions = st.multiselect(
            "Attribute",
            all_questions,
        )
        selected_questions = [
            question for question in all_questions if question in selected_questions
        ]
        if not selected_questions:
            selected_questions = all_questions

    # Initialize by_reference before columns so it can be used within column logic
    if "by_reference_checkbox" not in st.session_state:
        st.session_state["by_reference_checkbox"] = False

    by_reference = st.session_state["by_reference_checkbox"]

    col1, col2, col3, col4 = st.columns([0.60, 0.15, 0.1, 0.15])

    with col1:
        # Initialize session state for cross questions if not exists
        if "grids_selected_cross_questions" not in st.session_state:
            st.session_state["grids_selected_cross_questions"] = []

        if by_reference:
            cross_questions = get_cross_questions(
                config,
                for_="grids",
            )
            # When by_reference is True, show all cross questions as selected
            st.multiselect(
                "Cross questions",
                st.session_state["grids_selected_cross_questions"],
                default=st.session_state["grids_selected_cross_questions"],
                disabled=True,
            )
            selected_cross_questions = cross_questions
        else:
            cross_questions = get_cross_questions(
                config,
                for_="filters",
            )
            # Initialize the key-based multiselect with preserved selections
            if "grids_cross_questions_multiselect" not in st.session_state:
                st.session_state["grids_cross_questions_multiselect"] = (
                    st.session_state["grids_selected_cross_questions"]
                )

            selected_cross_questions = st.multiselect(
                "Cross questions",
                cross_questions,
                key="grids_cross_questions_multiselect",
            )
            # Update session state with current selection
            st.session_state["grids_selected_cross_questions"] = (
                selected_cross_questions
            )

    with col2:
        st.markdown('<div class="checkbox-container">', unsafe_allow_html=True)
        by_reference = st.checkbox("Cross by reference", key="by_reference_checkbox")
        show_question_text = st.checkbox("Show question text")
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        view_type = st.radio("View type", ["Grouped", "Detailed"], horizontal=False)

    with col4:
        decimal_precision = st.number_input(
            "Decimal precision", min_value=0, max_value=4, step=1
        )

    if question_groups and selected_questions and selected_cross_questions:
        try:
            df = build_statistical_significance_df(
                db,
                metadata_df,
                selected_cross_questions,
                selected_questions,
                config,
                questions_by_group,
                view_type=view_type,
                show_question_text=show_question_text,
            )
            if by_reference and view_type == "Detailed":
                # remove columns that contain "TOTAL" in any of the header levels
                df = df.loc[:, ~df.columns.get_level_values(1).str.contains("TOTAL")]

            html_table = create_html_table(df, decimal_precision)

            st.markdown(
                '<div style="overflow-x: auto; margin-bottom: 1.5rem;">{}</div>'.format(
                    html_table
                ),
                unsafe_allow_html=True,
            )

            # Encode the HTML content as UTF-8 bytes
            html_bytes = html_table.encode("utf-8")

            st.download_button(
                "Download table",
                data=html_bytes,
                file_name="statistical_significance.html",
                mime="text/html; charset=utf-8",
                type="primary",
            )

        except Exception as e:
            st.error(f"Error rendering table: {str(e)}")
