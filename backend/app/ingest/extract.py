import io
from pathlib import PurePosixPath


class ExtractionError(Exception):
    pass


TEXT_EXTS = {".txt", ".md"}


def extract_text(filename: str, data: bytes) -> str:
    """Best-effort plain text from a supported document. Raises ExtractionError on
    unsupported types or unreadable content."""
    ext = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if ext in TEXT_EXTS:
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # pypdf raises a zoo of types on corrupt files
            raise ExtractionError(f"unreadable pdf: {exc}") from exc
    raise ExtractionError(f"unsupported extension: {ext}")
