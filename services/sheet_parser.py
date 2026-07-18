"""PDF character sheet parsing and export via fillable form fields.

Works with fillable PDF character sheets (e.g. Pathfinder 2e official sheet,
or any PDF with AcroForm text fields). Non-fillable or image-only PDFs are
rejected with a clear error.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

from pypdf import PdfReader, PdfWriter

_log = logging.getLogger(__name__)


def parse_sheet(raw: bytes) -> dict[str, str]:
    """Extract every fillable text field from *raw* PDF bytes.

    Returns a flat ``{field_name: value}`` dict.
    Raises ``ValueError`` if the file isn't a valid fillable PDF.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("Expected raw PDF bytes, got " + type(raw).__name__)

    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError(f"Cannot read PDF: {exc}") from exc

    fields = reader.get_fields()
    if not fields:
        raise ValueError(
            "This PDF has no fillable form fields. "
            "Use an official fillable character sheet PDF."
        )

    data: dict[str, str] = {}
    for name, field_obj in fields.items():
        value = field_obj.get("/V")
        if value is not None:
            data[name] = str(value)
        else:
            data[name] = ""

    _log.debug("Parsed %d form fields from PDF", len(data))
    return data


def export_sheet(data: dict[str, Any], original_pdf: bytes) -> bytes:
    """Write *data* values back into the form fields of *original_pdf*.

    Returns the modified PDF as bytes.
    """
    if not original_pdf:
        raise ValueError("Original PDF is missing; upload your character sheet again.")

    reader = PdfReader(io.BytesIO(original_pdf))
    writer = PdfWriter(clone_from=reader)

    for page in writer.pages:
        writer.update_page_form_field_values(page, data, auto_regenerate=False)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def sheet_data_as_text(data: dict[str, str]) -> str:
    """Render sheet fields as readable text for the LLM context window."""
    return json.dumps(data, indent=2, ensure_ascii=False)
