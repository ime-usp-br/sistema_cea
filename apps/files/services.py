import hashlib
import os
import re
import uuid
from typing import Any

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from .models import FileAsset


def _sanitize_filename(filename: str | None) -> str:
    base = os.path.basename(filename or "arquivo")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:200]


def create_file_asset(
    *,
    application: Any,
    uploaded_by: Any,
    uploaded_file: UploadedFile,
    purpose: str,
) -> FileAsset:
    """Grava o arquivo no storage privado e registra apenas os metadados."""
    content = uploaded_file.read()
    checksum = hashlib.sha256(content).hexdigest()
    uploaded_file.seek(0)
    filename = _sanitize_filename(uploaded_file.name)
    storage_key = f"{purpose}/{application.pk}/{uuid.uuid4()}-{filename}"
    stored_key = default_storage.save(storage_key, uploaded_file)
    return FileAsset.objects.create(
        original_filename=filename,
        storage_key=stored_key,
        content_type=uploaded_file.content_type or None,
        size_bytes=len(content),
        sha256_checksum=checksum,
        purpose=purpose,
        application=application,
        uploaded_by=uploaded_by,
    )
