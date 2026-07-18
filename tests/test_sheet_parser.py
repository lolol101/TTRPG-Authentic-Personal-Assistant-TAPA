"""Tests for the PDF-based sheet parser."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    TextStringObject,
)

from services.sheet_parser import export_sheet, parse_sheet, sheet_data_as_text


def _make_pdf(fields: dict[str, str]) -> bytes:
    """Create a minimal fillable PDF with the given text fields."""
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    page = writer.pages[0]
    field_objs = ArrayObject()
    for name, value in fields.items():
        f = DictionaryObject()
        f[NameObject("/Type")] = NameObject("/Annot")
        f[NameObject("/Subtype")] = NameObject("/Widget")
        f[NameObject("/FT")] = NameObject("/Tx")
        f[NameObject("/T")] = TextStringObject(name)
        f[NameObject("/V")] = TextStringObject(value)
        f[NameObject("/Rect")] = ArrayObject(
            [FloatObject(0), FloatObject(0), FloatObject(100), FloatObject(20)]
        )
        ref = writer._add_object(f)
        field_objs.append(ref)
    acroform = DictionaryObject()
    acroform[NameObject("/Fields")] = field_objs
    writer._root_object[NameObject("/AcroForm")] = acroform
    page[NameObject("/Annots")] = field_objs
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestParseSheet:
    def test_basic_fields(self):
        pdf = _make_pdf({"CharacterName": "Valeros", "Level": "3", "STR": "18"})
        data = parse_sheet(pdf)
        assert data["CharacterName"] == "Valeros"
        assert data["Level"] == "3"
        assert data["STR"] == "18"

    def test_empty_field_value(self):
        pdf = _make_pdf({"Name": "", "HP": "42"})
        data = parse_sheet(pdf)
        assert data["Name"] == ""
        assert data["HP"] == "42"

    def test_not_bytes_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected raw PDF bytes"):
            parse_sheet("not bytes")

    def test_invalid_pdf_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot read PDF"):
            parse_sheet(b"not a pdf at all")

    def test_no_form_fields_raises(self):
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        buf = io.BytesIO()
        writer.write(buf)
        with pytest.raises(ValueError, match="no fillable form fields"):
            parse_sheet(buf.getvalue())


class TestExportSheet:
    def test_roundtrip(self):
        pdf = _make_pdf({"CharacterName": "Valeros", "Level": "3"})
        data = parse_sheet(pdf)
        data["Level"] = "5"

        new_pdf = export_sheet(data, pdf)
        data2 = parse_sheet(new_pdf)
        assert data2["Level"] == "5"
        assert data2["CharacterName"] == "Valeros"

    def test_add_field_value(self):
        pdf = _make_pdf({"Name": "", "Class": ""})
        data = parse_sheet(pdf)
        data["Name"] = "Seoni"
        data["Class"] = "Sorcerer"

        new_pdf = export_sheet(data, pdf)
        data2 = parse_sheet(new_pdf)
        assert data2["Name"] == "Seoni"
        assert data2["Class"] == "Sorcerer"

    def test_missing_original_raises(self):
        with pytest.raises(ValueError, match="Original PDF is missing"):
            export_sheet({"Level": "1"}, b"")

    def test_none_original_raises(self):
        with pytest.raises(ValueError, match="Original PDF is missing"):
            export_sheet({"Level": "1"}, None)


class TestSheetDataAsText:
    def test_produces_json(self):
        import json

        data = {"CharacterName": "Kyra", "Level": "7"}
        text = sheet_data_as_text(data)
        parsed = json.loads(text)
        assert parsed == data
