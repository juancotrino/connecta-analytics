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
    filter_df,
    get_cross_questions,
    build_statistical_significance_df,
    get_filter_questions,
    create_html_table,
)
from app.modules.utils import (
    read_sav_db,
    read_sav_metadata,
    load_json,
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

    st.markdown("### Study")

    categories = get_categories()
    product_category = st.selectbox("Product category", categories, index=None)

    if not product_category:
        return

    subcategories = get_subcategories(product_category)
    product_subcategory = st.selectbox("Product subcategory", subcategories, index=None)

    if not product_subcategory:
        return

    countries = get_study_countries(product_category, product_subcategory)
    selected_country = st.selectbox("Country", countries, index=None)

    if not selected_country:
        return

    study_names = get_studies_names(
        product_category, product_subcategory, selected_country, company
    )

    selected_studies = st.multiselect("Studies", study_names)

    if not selected_studies:
        return

    studies_data = download_studies_data(
        product_category,
        product_subcategory,
        selected_country,
        company,
        selected_studies,
    )

    with st.expander("Inspect variables"):
        sav_cols = st.columns(len(studies_data))
        studies_dbs = []
        for col, (study, data) in zip(sav_cols, studies_data.items()):
            col.markdown(f"### {study}")
            studies_dbs.append(read_sav_db(data["sav"]))
            metadata_df = read_sav_metadata(data["sav"])
            metadata_df["answer_options_count"] = (
                metadata_df["values"]
                .apply(lambda x: len(ast.literal_eval(x)) if x else 0)
                .astype(int)
            )
            col.dataframe(metadata_df, use_container_width=True)

        db = pd.concat(studies_dbs)

        col.dataframe(db)

    st.markdown("### Database filter")

    config = load_json(data["json"])["config"]

    fields = st.columns(len(config["filters"]))

    db = filter_df(fields, config["filters"], metadata_df, db)

    if db.empty:
        st.warning("The filters you applied to the database, return no records.")
        return

    st.markdown("### Statistical significance")

    question_groups = get_question_groups(product_category, product_subcategory)
    questions_by_group = get_questions(
        product_category, product_subcategory, question_groups
    )

    with st.expander("Filters"):
        col1, col2, col3 = st.columns([0.4, 0.45, 0.15])

        with col1:
            filter_questions = get_filter_questions(metadata_df)
            selected_questions = st.multiselect(
                "Attribute", filter_questions, key="filters_selected_questions"
            )

        with col2:
            cross_questions = get_cross_questions(config, for_="filters")
            selected_cross_questions = st.multiselect(
                "Cross questions",
                cross_questions,
                key="filters_selected_cross_questions",
            )

        with col3:
            decimal_precision = st.number_input(
                "Decimal precision",
                min_value=0,
                max_value=4,
                step=1,
                key="filters_decimal_precision",
            )

        if selected_questions and selected_cross_questions:
            try:
                df = build_statistical_significance_df(
                    db,
                    metadata_df,
                    selected_cross_questions,
                    selected_questions,
                    config,
                )

                html_table = create_html_table(df, decimal_precision)

                st.markdown(
                    '<div style="overflow-x: auto;">{}</div>'.format(html_table),
                    unsafe_allow_html=True,
                )

            except Exception as e:
                st.error(f"Error rendering table: {str(e)}")

    with st.expander("Grids"):
        col1, col2 = st.columns([0.4, 0.6])

        with col1:
            question_groups = st.multiselect(
                "Question group", sorted(question_groups, reverse=True)
            )

            questions_by_group = get_questions(
                product_category,
                product_subcategory,
                sorted(question_groups, reverse=True),
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
            by_reference = st.checkbox(
                "Cross by reference", key="by_reference_checkbox"
            )
            show_question_text = st.checkbox("Show question text")
            st.markdown("</div>", unsafe_allow_html=True)

        with col3:
            view_type = st.radio("View type", ["Grouped", "Detailed"], horizontal=False)

        with col4:
            decimal_precision = st.number_input(
                "Decimal precision", min_value=0, max_value=4, step=1
            )

        if selected_questions and selected_cross_questions:
            try:
                df = build_statistical_significance_df(
                    db,
                    metadata_df,
                    selected_cross_questions,
                    selected_questions,
                    config,
                    questions_by_group=questions_by_group,
                    by_moment=True,
                    view_type=view_type,
                    show_question_text=show_question_text,
                )

                html_table = create_html_table(df, decimal_precision)

                st.markdown(
                    '<div style="overflow-x: auto;">{}</div>'.format(html_table),
                    unsafe_allow_html=True,
                )

            except Exception as e:
                st.error(f"Error rendering table: {str(e)}")
