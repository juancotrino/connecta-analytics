import ast

import numpy as np
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
    df_to_html,
    filter_df,
    create_temp_df,
)
from app.modules.utils import read_sav_db, read_sav_metadata, load_json

# CSS to highlight headers and index of the dataframe
table_styles = [
    dict(selector="th", props="font-size: 1.0em; "),
    dict(selector="td", props="font-size: 1.0em; text-align: right"),
    dict(selector="tr:hover", props="background-color: lightgray"),
]


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

    st.markdown("### Database filter")

    config = load_json(data["json"])["config"]

    fields = st.columns(len(config["filters"]))

    db = filter_df(fields, config["filters"], metadata_df, db)

    if db.empty:
        st.warning("The filters you applied to the database, return no records.")

    # st.dataframe(db)

    st.markdown("### Statistical significance")

    question_groups = get_question_groups(product_category, product_subcategory)

    question_group = st.selectbox(
        "Question group", sorted(question_groups, reverse=True), index=None
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        group_questions = get_questions(
            product_category, product_subcategory, question_group
        )
        questions_names = [
            question["label"]
            for question in sorted(group_questions, key=lambda x: x["order"])
        ]
        selected_questions = st.multiselect(
            "Attribute",
            questions_names,
        )
        if not selected_questions:
            selected_questions = questions_names

    with col2:
        crossed_questions = st.multiselect(
            "Crossed questions", ["Question 1", "Question 2"]
        )
    with col3:
        view_type = st.radio("View type", ["Groupped", "Detailed"], horizontal=True)

    if not question_group:
        return

    df = create_temp_df(selected_questions, 1, view_type)

    if not selected_questions:
        return

    st.markdown(
        df
        # Make pandas.Styler from the DataFrame
        .style
        # .apply(lambda cell: np.where(cell != 0, "color: red", None), axis=1)
        # Format numbers to 2 decimal places, leave strings as is
        .format(
            lambda x: (
                f"{x:.2f}"
                if isinstance(x, (float, int)) and x % 1 != 0
                else f"{int(x)}"
                if isinstance(x, (float, int))
                else x
            )
        )
        # Apply CSS
        .set_table_styles(table_styles)
        # Convert DataFrame Styler object to formatted HTML text
        .to_html(escape=False, border=5),
        # Streamlit stop complaining
        unsafe_allow_html=True,
    )
