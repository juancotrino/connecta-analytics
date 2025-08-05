import time
import uuid
from functools import partial

import pandas as pd

import streamlit as st
from streamlit_tags import st_tags

from app.modules.utils import (
    _to_show,
    get_user_name_from_id,
    get_users,
    get_user_id_from_name,
)
from app.modules.business_definition import (
    get_business_data,
    get_question_types,
    save_business_data,
    create_category_tree,
    get_category_tree_groups,
    get_category_id,
    get_subcategory_id,
    get_questions,
    get_question_type_by_id,
    get_question_type_id,
    create_question,
    get_group_id,
    create_group,
)
from app.modules.processing_viewer import (
    get_categories,
    get_subcategories,
)
# from app.modules.help import questions_to_markdown


def main():
    st.write("Here you can set business general data.")

    st.write("## Business Data")

    with st.expander("Edit business Data"):
        business_data = get_business_data()
        users = get_users()
        users_names = [user["name"] for user in users]

        # --- Session state setup ---
        if "composed_dict" not in st.session_state:
            st.session_state.composed_dict = {
                k: v.copy() for k, v in business_data.items()
            }

        if "deletion_warning" not in st.session_state:
            st.session_state.deletion_warning = False

        if "editor_version" not in st.session_state:
            st.session_state.editor_version = 0

        # --- Select category ---
        selected_key = st.selectbox(
            "Select data to edit",
            options=list(business_data.keys()),
            format_func=_to_show,
        )

        # --- Get current values ---
        current_values = st.session_state.composed_dict[selected_key]
        df_editable = pd.DataFrame(current_values, columns=[_to_show(selected_key)])

        # --- Data editor ---
        editor_key = f"editor_{selected_key}_{st.session_state.editor_version}"
        if selected_key == "consultants":
            df_editable["Consultants"] = df_editable["Consultants"].apply(
                lambda x: get_user_name_from_id(x)
            )
            edited_df = st.data_editor(
                df_editable,
                num_rows="dynamic",
                key=editor_key,
                hide_index=True,
                column_config={
                    "Consultants": st.column_config.SelectboxColumn(
                        "Consultants",
                        options=users_names,
                        required=True,
                    ),
                },
            )

            edited_df["Consultants"] = edited_df["Consultants"].apply(
                lambda x: get_user_id_from_name(x)
            )
        else:
            edited_df = st.data_editor(
                df_editable, num_rows="dynamic", key=editor_key, hide_index=True
            )

        edited_values = edited_df[_to_show(selected_key)].dropna().tolist()

        # --- Check for deletion by comparing lengths ---
        if len(edited_values) < len(business_data[selected_key]):
            st.session_state.deletion_warning = True
            st.session_state.composed_dict[selected_key] = business_data[
                selected_key
            ].copy()
            st.session_state.editor_version += 1  # Force reset editor
            st.error(
                "🚫 Cannot delete existing items. Only additions are allowed.",
            )
            time.sleep(2)
            st.rerun()
        else:
            st.session_state.deletion_warning = False
            # Add only new items
            for val in edited_values:
                if val not in current_values:
                    st.session_state.composed_dict[selected_key].append(val)

        # --- Save button ---
        if st.button("Save changes"):
            if st.session_state.deletion_warning:
                st.warning("Changes not saved due to deletion not allowed.")
            else:
                save_business_data(st.session_state.composed_dict)
                st.success("Changes saved successfully.")
                get_business_data.clear()

    st.write("## Survey Data")
    with st.expander("Edit survey configuration"):
        category = st.selectbox(
            "Category",
            get_categories() + ["New"],
            format_func=_to_show,
            index=None,
            key="category_select",
        )

        if category == "New":
            category = st.text_input(
                "New Category",
                key="category_input",
                placeholder="Enter new category name",
            )
            subcategory = st.text_input(
                "New Subcategory",
                key="subcategory_input",
                placeholder="Enter new subcategory name",
            )
        elif category is None:
            return
        else:
            subcategory = st.selectbox(
                "Subcategory",
                get_subcategories(category) + ["New"],
                format_func=_to_show,
                index=None,
                key="subcategory_select",
            )

            if subcategory == "New":
                subcategory = st.text_input(
                    "New Subcategory",
                    key="subcategory_only_input",
                    placeholder="Enter new subcategory name",
                )

        if (category and subcategory) and (
            category not in get_categories()
            or subcategory not in get_subcategories(category)
        ):
            create = st.button("Create", type="primary")
            if create and category and subcategory:
                create_category_tree(category, subcategory)
                st.success("Category created successfully.")
                get_categories.clear()
                get_subcategories.clear()
                st.rerun()
            elif create and not category and not subcategory:
                st.warning("Nothing to create.")
        elif category and subcategory:
            category_id = get_category_id(category)
            subcategory_id = get_subcategory_id(subcategory, category_id)
            existing_groups = get_category_tree_groups(category_id, subcategory_id)

            existing_groups_names = [
                group["name"]
                for group in sorted(existing_groups, key=lambda x: x["order"])
            ]

            groups: list[str] = st_tags(
                label="Groups",
                value=existing_groups_names,
                suggestions=["FILTERS", "KPI'S PRINCIPALES"],
                maxtags=10,
                key="groups",
            )

            if not groups:
                return

            groups = [group.upper() for group in groups]

            questions = {}

            question_editor_columns = [
                "code",
                "label",
                "question_type",
                "sorted_by",
                "sort_order",
            ]
            question_types = get_question_types()
            # question_types_help = questions_to_markdown(question_types)
            question_types_codes = [
                question_type["code"] for question_type in question_types
            ]

            st.markdown("### Questions by group")

            # with st.expander("Question types help", expanded=False):
            #     st.markdown(question_types_help)

            def load_questions(
                questions: pd.DataFrame,
                group_id: str | None,
                category_id: str,
                subcategory_id: str,
                current_questions: list[dict[str, str]],
                key: str,
                group: str,
                category: str,
                subcategory: str,
            ):
                if group_id is None:
                    group_id = create_group(group, category_id, subcategory_id)
                    get_category_tree_groups.clear(category_id, subcategory_id)
                    get_group_id.clear(group, category_id, subcategory_id)
                    # Clear any existing questions in session state for this new group
                    if f"current_questions_{group}" in st.session_state:
                        del st.session_state[f"current_questions_{group}"]
                    # Get fresh questions list from database
                    current_questions = get_questions(category, subcategory, group)
                    st.session_state[f"current_questions_{group}"] = current_questions

                for i, question in questions.iterrows():
                    question_type_id = get_question_type_id(question["question_type"])
                    create_question(
                        question["code"],
                        question["label"],
                        len(current_questions) + i + 1,
                        subcategory_id,
                        group_id,
                        category_id,
                        question_type_id,
                        question["sorted_by"],
                        question["sort_order"],
                    )
                # Clear cache
                get_questions.clear(category, subcategory, group)

                # Refresh the list and store in session
                st.session_state[f"current_questions_{group}"] = get_questions(
                    category, subcategory, group
                )
                # Change the key of the data editor to start over.
                st.session_state[key] = str(uuid.uuid4())

            editor_dataframe_template = pd.DataFrame(columns=question_editor_columns)

            for group in groups:
                key = f"dek_{group}"
                # Define a variable as a key of the data editor.
                if key not in st.session_state:
                    st.session_state[key] = str(uuid.uuid4())

                group_id = get_group_id(group, category_id, subcategory_id)
                if f"current_questions_{group}" in st.session_state:
                    current_questions = st.session_state[f"current_questions_{group}"]
                elif group_id:
                    current_questions = get_questions(category, subcategory, group)
                    st.session_state[f"current_questions_{group}"] = current_questions
                else:
                    current_questions = []

                st.markdown(f"#### {group}")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### Add questions")
                    questions[group] = st.data_editor(
                        editor_dataframe_template.copy(),
                        num_rows="dynamic",
                        key=st.session_state[key],
                        hide_index=True,
                        column_config={
                            "code": st.column_config.TextColumn(
                                "Question Code",
                                required=True,
                            ),
                            "label": st.column_config.TextColumn(
                                "Question Label",
                                required=True,
                            ),
                            "question_type": st.column_config.SelectboxColumn(
                                "Question Type",
                                options=question_types_codes,
                                required=True,
                            ),
                            "sorted_by": st.column_config.SelectboxColumn(
                                "Sorted By",
                                options=["options", "values"],
                                required=True,
                            ),
                            "sort_order": st.column_config.SelectboxColumn(
                                "Sort Order",
                                options=["asc", "desc", "original"],
                                required=True,
                            ),
                        },
                    )

                    if not questions[group].empty:
                        if st.button(
                            "Add questions",
                            type="primary",
                            key=f"add_questions_{group}",
                            on_click=partial(
                                load_questions,
                                questions[group],
                                group_id,
                                category_id,
                                subcategory_id,
                                current_questions,
                                key,
                                group,
                                category,
                                subcategory,
                            ),
                        ):
                            st.success("Questions added successfully.")
                            st.rerun()

                with col2:
                    st.markdown("##### Current questions")
                    current_questions_df = pd.DataFrame(
                        current_questions,
                        columns=[
                            "category_id",
                            "subcategory_id",
                            "group_id",
                            "code",
                            "label",
                            "question_type_id",
                            "sorted_by",
                            "sort_order",
                            "order",
                        ],
                    )
                    current_questions_df["question_type"] = current_questions_df[
                        "question_type_id"
                    ].apply(lambda x: get_question_type_by_id(x)["code"])
                    current_questions_df = current_questions_df.sort_values(
                        by="order"
                    ).reset_index(drop=True)
                    current_questions_df = current_questions_df[question_editor_columns]
                    st.dataframe(
                        current_questions_df,
                        column_config={
                            "code": "Question Code",
                            "label": "Question Label",
                            "question_type": "Question Type",
                            "sorted_by": "Sorted By",
                            "sort_order": "Sort Order",
                        },
                        hide_index=True,
                        use_container_width=True,
                    )


# TODO: Make available the option to upload a SAV file to take the questions from it. So that it recomends the questions to add.
# TODO: Add a validator if a SAV is loaded, that compares all the questions within the SAV and the ones that were added to the survey. If there are any missing, it should show a warning.
