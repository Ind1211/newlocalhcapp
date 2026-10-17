"""
Thin wrapper around Azure Blob Storage — every other module talks to this file, not
to the azure-storage-blob SDK directly, so the storage backend could be swapped
later without touching the rest of the app. (Originally backed by MinIO; swapped
to Azure Blob Storage for the Azure Container Apps deployment — see
claude/azure-container-apps-deployment-plan.md in the project notes.)
"""

import os
import uuid

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

CONTAINER_NAME = "patient-documents"

_client: BlobServiceClient | None = None


def get_client() -> BlobServiceClient:
    global _client
    if _client is None:
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            raise RuntimeError(
                "AZURE_STORAGE_CONNECTION_STRING is not set — required to connect to "
                "Azure Blob Storage (see claude/azure-container-apps-deployment-plan.md)."
            )
        _client = BlobServiceClient.from_connection_string(connection_string)
        container_client = _client.get_container_client(CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container()
    return _client


def _container_client():
    return get_client().get_container_client(CONTAINER_NAME)


def upload_document(patient_id: str, filename: str, content: bytes, content_type: str) -> str:
    """Returns the storage key — a patient-scoped, collision-proof path, not the
    original filename, since two documents from different patients (or the same
    patient) could otherwise share a name."""
    key = f"{patient_id}/{uuid.uuid4()}-{filename}"
    blob_client = _container_client().get_blob_client(key)
    blob_client.upload_blob(
        content, overwrite=True, content_settings=ContentSettings(content_type=content_type),
    )
    return key


def download_document(storage_key: str) -> bytes:
    blob_client = _container_client().get_blob_client(storage_key)
    return blob_client.download_blob().readall()


def delete_document(storage_key: str) -> None:
    blob_client = _container_client().get_blob_client(storage_key)
    try:
        blob_client.delete_blob()
    except ResourceNotFoundError:
        # Already gone, or never existed — deleting the DB row should still
        # succeed either way, so this doesn't re-raise.
        pass
