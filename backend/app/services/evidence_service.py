"""
Evidence service — business logic for AssetEvidence operations and secure uploads.
"""
import logging
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.exceptions import InvalidFileError
from backend.app.models.asset import Asset
from backend.app.models.asset_evidence import AssetEvidence, EvidenceClassification
from backend.app.repositories.asset_repository import AssetRepository
from backend.app.repositories.evidence_repository import EvidenceRepository
from backend.app.schemas.asset_evidence import AssetEvidenceCreate
from backend.app.services.base import BaseService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "application/octet-stream",
}
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class EvidenceService(BaseService):
    """Service layer for AssetEvidence operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = EvidenceRepository(session)
        self._asset_repo = AssetRepository(session)

    async def get_asset(self, asset_id: str) -> Asset | None:
        """Retrieve asset by UUID."""
        return await self._asset_repo.get_by_id(asset_id)

    async def upload_evidence_file(
        self,
        file: UploadFile,
        asset_id: str | None = None,
        caption: str | None = None,
        classification: EvidenceClassification = EvidenceClassification.VERIFIED_STRUCTURE,
    ) -> tuple[str, str, int, AssetEvidence | None]:
        """
        Securely validate, persist image bytes to UPLOAD_DIR/evidence, and optionally
        register an AssetEvidence row in the database if an asset_id is provided.

        Returns:
            tuple of (file_path, unique_filename, size_bytes, evidence_record)
        """
        if not file.filename:
            raise InvalidFileError("Uploaded file has no filename.")

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise InvalidFileError(
                f"Unsupported file extension '{ext}'. Permitted extensions: {allowed}"
            )

        if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
            raise InvalidFileError(
                f"Unsupported MIME type '{file.content_type}'. "
                "Permitted image types: JPEG, PNG, WebP, TIFF."
            )

        contents = await file.read()
        size_bytes = len(contents)

        if size_bytes == 0:
            raise InvalidFileError("Uploaded file is empty (0 bytes).")

        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            size_mb = size_bytes / (1024 * 1024)
            raise InvalidFileError(
                f"File size ({size_mb:.2f} MB) exceeds maximum limit of {max_mb:.0f} MB."
            )

        # Sanitize filename and generate server-side unique name
        raw_stem = Path(file.filename).stem
        safe_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_stem)[:40].strip("_") or "evidence"
        unique_filename = f"{uuid.uuid4().hex[:12]}_{safe_stem}{ext}"

        settings = get_settings()
        evidence_dir = (settings.UPLOAD_DIR / "evidence").resolve()
        evidence_dir.mkdir(parents=True, exist_ok=True)

        dest_path = (evidence_dir / unique_filename).resolve()
        if not dest_path.is_relative_to(evidence_dir):
            raise InvalidFileError("Path traversal detected in upload filename.")

        dest_path.write_bytes(contents)
        file_path = f"/uploads/evidence/{unique_filename}"
        logger.info(f"Persisted evidence file: {dest_path} ({size_bytes} bytes)")

        # Link to asset in DB if asset_id provided
        evidence_record: AssetEvidence | None = None
        if asset_id:
            asset = await self._asset_repo.get_by_id(asset_id)
            if asset:
                evidence_record = await self._repo.create(
                    asset_id=asset_id,
                    filename=unique_filename,
                    file_path=file_path,
                    caption=caption or file.filename or "Uploaded evidence photograph",
                    classification=classification,
                    is_sample=False,
                )
                logger.info(
                    f"Created AssetEvidence record {evidence_record.id!r} for asset {asset_id!r}"
                )
            else:
                logger.warning(
                    f"Asset '{asset_id}' not found. Saved file to disk without AssetEvidence link."
                )

        return file_path, unique_filename, size_bytes, evidence_record

    async def create_evidence(self, data: AssetEvidenceCreate) -> AssetEvidence | None:
        """Create a new evidence record for an asset. Returns None if asset doesn't exist."""
        asset = await self._asset_repo.get_by_id(data.asset_id)
        if asset is None:
            logger.warning(f"Cannot create evidence: Asset '{data.asset_id}' not found.")
            return None

        # Check for duplicate
        existing = await self._repo.get_by_asset_and_filename(data.asset_id, data.filename)
        if existing:
            logger.info(f"Evidence {data.filename} already exists for asset {data.asset_id}.")
            return existing

        evidence = await self._repo.create(**data.model_dump(exclude_none=False))
        logger.info(f"Evidence created: id={evidence.id!r} filename={evidence.filename!r}")
        return evidence

    async def list_for_asset(self, asset_id: str) -> list[AssetEvidence]:
        """List all visual evidence items for a given asset."""
        return await self._repo.list_for_asset(asset_id)

    async def get_evidence(self, evidence_id: str) -> AssetEvidence | None:
        """Retrieve single evidence record by ID."""
        return await self._repo.get_by_id(evidence_id)
