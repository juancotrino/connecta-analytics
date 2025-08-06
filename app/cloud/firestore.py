from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Initialize Firestore
db = firestore.Client()


def create_document(
    parent_collection_name: str,
    parent_document_name: str,
    child_collection_name: str,
    data: dict,
) -> str:
    # Reference to your nested root document
    root_doc = db.collection(parent_collection_name).document(parent_document_name)
    cat_ref = root_doc.collection(child_collection_name).document()
    cat_ref.set(data)
    return cat_ref.id


def get_document(
    parent_collection_name: str,
    parent_document_name: str,
    child_collection_name: str,
    child_document_name: str,
) -> str | None:
    """
    Get a document ID by its name from a nested collection in Firestore.

    Args:
        parent_collection_name: Name of the parent collection
        parent_document_name: ID of the parent document
        child_collection_name: Name of the child collection
        child_document_name: Name of the document to find

    Returns:
        str | None: The document ID if found, None otherwise
    """
    try:
        # Get reference to the parent document
        root_doc = db.collection(parent_collection_name).document(parent_document_name)

        # Query the child collection
        query = (
            root_doc.collection(child_collection_name)
            .where(filter=FieldFilter("name", "==", child_document_name))
            .limit(1)
            .stream()
        )

        # Return the first matching document ID if found
        for doc in query:
            return doc.id

        print(
            f"No document found with name '{child_document_name}' in "
            f"{parent_collection_name}/{parent_document_name}/{child_collection_name}"
        )
        return None

    except Exception as e:
        print(f"Error getting document: {str(e)}")
        return None
