import io
import uuid
from datetime import datetime, timezone

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import settings


def _get_blob_service() -> BlobServiceClient:
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not configured")
    return BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)


def _container_client():
    service = _get_blob_service()
    container = service.get_container_client(settings.AZURE_CONTAINER_NAME)
    # Ensure container exists
    if not container.exists():
        container.create_container()
    return container


def upload_blob_file(prefix: str, user_id: uuid.UUID, file_bytes: bytes, file_name: str, mime_type: str) -> str:
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else "bin"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    blob_name = f"{prefix}/{user_id}/{ts}_{uuid.uuid4().hex[:8]}.{ext}"

    container = _container_client()
    container.upload_blob(
        name=blob_name,
        data=file_bytes,
        overwrite=False,
        content_settings=ContentSettings(content_type=mime_type),
    )
    return blob_name


def upload_capture_file(user_id: uuid.UUID, file_bytes: bytes, file_name: str, mime_type: str) -> str:
    return upload_blob_file("captures", user_id, file_bytes, file_name, mime_type)


def upload_task_description_file(user_id: uuid.UUID, file_bytes: bytes, file_name: str, mime_type: str) -> str:
    return upload_blob_file("task-descriptions", user_id, file_bytes, file_name, mime_type)


def delete_capture_file(storage_path: str) -> None:
    container = _container_client()
    container.delete_blob(storage_path)


def get_blob_download_url(storage_path: str, expiry_minutes: int = 60) -> str:
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions
    import logging
    from azure.core.credentials import AzureNamedKeyCredential

    logger = logging.getLogger(__name__)
    container = _container_client()
    
    try:
        # Verify blob exists
        blob_client = container.get_blob_client(storage_path)
        if not blob_client.exists():
            logger.error(f"Blob not found: {storage_path}")
            raise FileNotFoundError(f"Blob not found: {storage_path}")
        
        # Extract account key from connection string
        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        account_key = None
        for part in conn_str.split(";"):
            if part.startswith("AccountKey="):
                account_key = part.split("=", 1)[1]
                break
        
        if not account_key:
            raise ValueError("Could not extract account key from connection string")
        
        sas_token = generate_blob_sas(
            account_name=container.account_name,
            container_name=settings.AZURE_CONTAINER_NAME,
            blob_name=storage_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + __import__("datetime").timedelta(minutes=expiry_minutes),
        )
        url = f"https://{container.account_name}.blob.core.windows.net/{settings.AZURE_CONTAINER_NAME}/{storage_path}?{sas_token}"
        logger.info(f"Generated SAS URL for {storage_path}")
        return url
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to generate SAS URL for {storage_path}: {e}")
        raise
