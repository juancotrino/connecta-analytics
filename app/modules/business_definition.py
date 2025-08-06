import streamlit as st

from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore

from app.cloud.firestore import create_document, get_document
from app.cloud.cloud_storage import CloudStorageClient
from app.modules.utils import _to_code


@st.cache_data(show_spinner=False)
def get_business_data() -> dict[str, str] | None:
    db = firestore.client()
    document = db.collection("settings").document("business_data").get()

    if document.exists:
        business_data = document.to_dict()
        return business_data


@st.cache_data(show_spinner=False)
def get_question_types() -> list[str] | None:
    db = firestore.client()
    documents = (
        db.collection("settings")
        .document("survey_config")
        .collection("question_types")
        .stream()
    )
    question_types = [document.to_dict() for document in documents]
    return question_types


@st.cache_data(show_spinner=False)
def get_question_type_by_id(question_type_id: str) -> dict[str, str] | None:
    db = firestore.client()
    document = (
        db.collection("settings")
        .document("survey_config")
        .collection("question_types")
        .document(question_type_id)
        .get()
    )
    if document.exists:
        return document.to_dict()
    return None


@st.cache_data(show_spinner=False)
def get_category_tree_groups(category_id: str, subcategory_id: str) -> list[str]:
    db = firestore.client()
    documents = (
        db.collection("settings")
        .document("survey_config")
        .collection("groups")
        .where(filter=FieldFilter("category_id", "==", category_id))
        .where(filter=FieldFilter("subcategory_id", "==", subcategory_id))
        .stream()
    )
    groups = [document.to_dict() for document in documents]
    return groups


@st.cache_data(show_spinner=False)
def get_category_id(category_name: str | None) -> str | None:
    if not category_name:
        return None
    db = firestore.client()
    category_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("categories")
        .where(filter=FieldFilter("name", "==", category_name))
        .limit(1)
        .stream()
    )
    for category_doc in category_query:
        return category_doc.id
    print(f"No category found with name: {category_name}")
    return None


@st.cache_data(show_spinner=False)
def get_subcategory_id(
    subcategory_name: str | None, category_id: str | None
) -> str | None:
    if not subcategory_name or not category_id:
        return None
    db = firestore.client()
    subcategory_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("subcategories")
        .where(filter=FieldFilter("name", "==", subcategory_name))
        .where(filter=FieldFilter("category_id", "==", category_id))
        .limit(1)
        .stream()
    )
    for subcategory_doc in subcategory_query:
        return subcategory_doc.id
    print(f"No subcategory found with name: {subcategory_name}")
    return None


@st.cache_data(show_spinner=False)
def get_group_id(
    group_name: str | None, category_id: str | None, subcategory_id: str | None
) -> str | None:
    if not group_name or not subcategory_id:
        return None
    db = firestore.client()
    group_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("groups")
        .where(filter=FieldFilter("name", "==", group_name))
        .where(filter=FieldFilter("category_id", "==", category_id))
        .where(filter=FieldFilter("subcategory_id", "==", subcategory_id))
        .limit(1)
        .stream()
    )
    for group_doc in group_query:
        return group_doc.id
    return None


@st.cache_data(show_spinner=False)
def get_question_type_id(question_type: str | None = None) -> str | None:
    if not question_type:
        return None
    db = firestore.client()
    question_type_query = (
        db.collection("settings")
        .document("survey_config")
        .collection("question_types")
        .where(filter=FieldFilter("code", "==", question_type))
        .limit(1)
        .stream()
    )
    for question_type_doc in question_type_query:
        return question_type_doc.id
    print(f"No question_type found with code: {question_type}")
    return None


@st.cache_data(show_spinner=False)
def get_questions(
    category_name: str | None = None,
    subcategory_name: str | None = None,
    group_name: str | None = None,
    question_type: str | None = None,
) -> list[dict[str, str]]:
    db = firestore.client()
    category_id = get_category_id(category_name)
    subcategory_id = get_subcategory_id(subcategory_name, category_id)
    group_id = get_group_id(group_name, category_id, subcategory_id)
    question_type_id = get_question_type_id(question_type)

    questions_ref = (
        db.collection("settings").document("survey_config").collection("questions")
    )
    if category_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("category_id", "==", category_id)
        )
    if subcategory_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("subcategory_id", "==", subcategory_id)
        )
    if group_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("group_id", "==", group_id)
        )
    if question_type_id:
        questions_ref = questions_ref.where(
            filter=FieldFilter("question_type_id", "==", question_type_id)
        )

    questions_query = questions_ref.stream()
    questions = [question_doc.to_dict() for question_doc in questions_query]
    return questions


def get_groups(category_id: str, subcategory_id: str) -> list[str]:
    db = firestore.client()
    groups_ref = (
        db.collection("settings").document("survey_config").collection("groups")
    )
    if category_id:
        groups_ref = groups_ref.where(
            filter=FieldFilter("category_id", "==", category_id)
        )
    if subcategory_id:
        groups_ref = groups_ref.where(
            filter=FieldFilter("subcategory_id", "==", subcategory_id)
        )
    groups_query = groups_ref.stream()
    groups = [group_doc.to_dict() for group_doc in groups_query]
    return groups


def save_business_data(business_data: dict):
    db = firestore.client()
    db.collection("settings").document("business_data").set(business_data)


def create_category_in_db(category_name: str) -> str:
    data = {"name": category_name}
    return create_document("settings", "survey_config", "categories", data)


def create_subcategory_in_db(category_ref: str, subcategory_name: str) -> str:
    data = {"name": subcategory_name, "category_id": category_ref}
    return create_document("settings", "survey_config", "subcategories", data)


def create_category_tree_in_storage(category_name: str, subcategory_name: str):
    gcs = CloudStorageClient("connecta-app-1-service-processing")
    return gcs.create_folder(f"databases/{category_name}/{subcategory_name}")


def create_category_tree(category_name: str, subcategory_name: str) -> tuple[str, str]:
    category_name = _to_code(category_name)
    subcategory_name = _to_code(subcategory_name)
    category_ref = get_document(
        "settings", "survey_config", "categories", category_name
    )
    if not category_ref:
        category_ref = create_category_in_db(category_name)
    subcategory_ref = create_subcategory_in_db(category_ref, subcategory_name)
    create_category_tree_in_storage(category_name, subcategory_name)
    return category_ref, subcategory_ref


def create_question(
    code: str,
    label: str,
    order: int,
    subcategory_id: str,
    group_id: str,
    category_id: str,
    question_type_id: str,
    sorted_by: str,
    sort_order: str,
) -> str:
    data = {
        "code": code,
        "label": label,
        "order": order,
        "subcategory_id": subcategory_id,
        "group_id": group_id,
        "category_id": category_id,
        "question_type_id": question_type_id,
        "sorted_by": sorted_by,
        "sort_order": sort_order,
    }
    return create_document("settings", "survey_config", "questions", data)


def create_group(group_name: str, category_id: str, subcategory_id: str) -> str:
    groups = get_groups(category_id=category_id, subcategory_id=subcategory_id)
    data = {
        "name": group_name,
        "category_id": category_id,
        "subcategory_id": subcategory_id,
        "order": len(groups) + 1,
    }
    return create_document("settings", "survey_config", "groups", data)
