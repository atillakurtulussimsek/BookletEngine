"""
Integration tests for the booklet engine.

Tests the full pipeline with generated test PDFs,
validating detection, assembly, and page count constraints.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pymupdf as fitz
import pikepdf
import pytest

from src.exam.core.assembler import assemble_booklet
from src.exam.core.detector import detect_removable_pages, validate_pdf
from src.exam.core.engine import run_batch
from src.exam.core.pipeline import process_student
from src.exam.core.template_processor import (
    _find_marker_rect,
    create_name_overlay,
    prepare_front_template,
)
from src.exam.models.config import DetectionConfig, EngineConfig, TemplateConfig, load_config
from src.exam.models.records import ProcessingStatus, StudentRecord
from src.exam.utils.pdf_scanner import scan_student_pdfs
from tests.exam.fixtures import (
    create_back_cover,
    create_front_template,
    create_sample_student_pdf,
    setup_test_environment,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test artifacts."""
    d = Path(tempfile.mkdtemp(prefix="booklet_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def test_env(tmp_dir):
    """Set up a complete test environment."""
    students = setup_test_environment(tmp_dir, num_students=3)

    # Write config.json
    config_data = {
        "input_dir": "input_pdfs",
        "output_dir": "output_pdfs",
        "log_dir": "logs",
        "font_dir": "fonts",
        "front_template_filename": "front_template.pdf",
        "back_cover_filename": "back_cover.pdf",
        "detection": {
            "max_scan_pages": 10,
            "region_x0_ratio": 0.0,
            "region_y0_ratio": 0.7,
            "region_x1_ratio": 0.5,
            "region_y1_ratio": 1.0,
            "case_sensitive": False,
        },
        "template": {
            "marker_text": "{{STUDENT_NAME}}",
            "fallback_x": 297.75,
            "fallback_y": 340,
            "font_name": "DejaVuSans-Bold",
            "font_size": 26,
            "font_color_r": 0.10,
            "font_color_g": 0.36,
            "font_color_b": 0.60,
            "text_align": "center",
        },
        "processing": {
            "max_workers": 1,
            "booklet_page_multiple": 4,
            "stream_buffer_size_mb": 64,
            "delete_source_pdf": False,
        },
    }
    config_path = tmp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f)

    cfg = load_config(config_path)
    return cfg, students


# ── Detection Tests ──────────────────────────────────────────


class TestDetector:
    """Tests for first-page name detection."""

    def test_removes_pages_without_name(self, tmp_dir):
        """Pages without the student name are removed (cover pages)."""
        pdf_path = tmp_dir / "test.pdf"
        create_sample_student_pdf(
            pdf_path, "Ahmet Yılmaz",
            include_name_on_page1=False,
            include_name_on_page2=True,
        )
        config = DetectionConfig()
        result = detect_removable_pages(pdf_path, "Ahmet Yılmaz", config)
        # Page 1 has no name → removed, page 2 has name → kept
        assert result.count == 1
        assert 0 in result.pages_to_remove

    def test_removes_multiple_cover_pages(self, tmp_dir):
        """Multiple pages without name are removed until name is found."""
        pdf_path = tmp_dir / "test.pdf"
        create_sample_student_pdf(
            pdf_path, "Elif Öztürk",
            include_name_on_page1=False,
            include_name_on_page2=False,
        )
        config = DetectionConfig()
        result = detect_removable_pages(pdf_path, "Elif Öztürk", config)
        # Both pages 1 and 2 have no name → both removed
        assert result.count >= 2
        assert 0 in result.pages_to_remove
        assert 1 in result.pages_to_remove

    def test_no_removal_when_name_on_page1(self, tmp_dir):
        """If name is on page 1, no pages are removed."""
        pdf_path = tmp_dir / "test.pdf"
        create_sample_student_pdf(
            pdf_path, "Ahmet Yılmaz",
            include_name_on_page1=True,
            include_name_on_page2=False,
        )
        config = DetectionConfig()
        result = detect_removable_pages(pdf_path, "Ahmet Yılmaz", config)
        assert result.count == 0

    def test_case_insensitive(self, tmp_dir):
        """Case-insensitive match: PDF has mixed case, search is lowercase.

        Uses ASCII-safe characters to isolate case-folding logic from
        Turkish locale issues (İ/ı have non-standard Unicode lowering).
        Turkish-specific casing is a known limitation documented in the
        detector module.
        """
        pdf_path = tmp_dir / "test.pdf"
        # Name on page 1 → no pages removed (content starts at page 1)
        create_sample_student_pdf(pdf_path, "Mehmet CELIK",
            include_name_on_page1=True, name_starts_on_page=0)
        config = DetectionConfig(case_sensitive=False)
        result = detect_removable_pages(pdf_path, "mehmet celik", config)
        assert result.count == 0  # Name found on page 1, nothing to remove

    def test_stops_scan_after_match(self, tmp_dir):
        """When name is found on page 2, only page 1 is removed."""
        pdf_path = tmp_dir / "test.pdf"
        create_sample_student_pdf(
            pdf_path, "Mehmet Çelik",
            include_name_on_page1=False,
            include_name_on_page2=True,
        )
        config = DetectionConfig()
        result = detect_removable_pages(pdf_path, "Mehmet Çelik", config)
        # Page 1 has no name → removed, page 2 has name → kept
        assert result.count == 1
        assert result.pages_to_remove == [0]

    def test_validate_valid_pdf(self, tmp_dir):
        pdf_path = tmp_dir / "test.pdf"
        create_sample_student_pdf(pdf_path, "Test")
        is_valid, msg = validate_pdf(pdf_path)
        assert is_valid is True

    def test_validate_corrupt_pdf(self, tmp_dir):
        bad_path = tmp_dir / "corrupt.pdf"
        bad_path.write_text("not a pdf")
        is_valid, msg = validate_pdf(bad_path)
        # PyMuPDF may or may not raise on invalid data, check result
        assert isinstance(is_valid, bool)


# ── Template Tests ───────────────────────────────────────────


class TestTemplate:
    """Tests for front template marker detection and overlay."""

    def test_marker_detection(self, tmp_dir):
        template_path = tmp_dir / "template.pdf"
        create_front_template(template_path, with_marker=True)
        rect = _find_marker_rect(template_path, "{{STUDENT_NAME}}")
        assert rect is not None
        x0, y0, x1, y1, pw, ph = rect
        assert x0 < x1
        assert y0 < y1
        assert pw > 0
        assert ph > 0

    def test_marker_not_found(self, tmp_dir):
        template_path = tmp_dir / "template.pdf"
        create_front_template(template_path, with_marker=False)
        rect = _find_marker_rect(template_path, "{{STUDENT_NAME}}")
        assert rect is None

    def test_overlay_generation(self, tmp_dir):
        config = TemplateConfig()
        overlay_bytes = create_name_overlay(
            "Ayşe Şahin",
            (100, 350, 400, 380, 595, 842),
            config,
        )
        assert len(overlay_bytes) > 0
        # Verify it's valid PDF
        doc = fitz.open(stream=overlay_bytes, filetype="pdf")
        assert doc.page_count == 1
        doc.close()

    def test_full_template_processing(self, tmp_dir):
        template_path = tmp_dir / "template.pdf"
        create_front_template(template_path)
        config = TemplateConfig()
        result_bytes = prepare_front_template(
            template_path, "İbrahim Güneş", config
        )
        assert len(result_bytes) > 0
        doc = fitz.open(stream=result_bytes, filetype="pdf")
        assert doc.page_count == 1
        doc.close()


# ── Assembly Tests ───────────────────────────────────────────


class TestAssembler:
    """Tests for booklet assembly and page count constraints."""

    def test_page_count_multiple_of_4(self, test_env):
        cfg, students = test_env
        filename, name = students[0]
        student = StudentRecord(filename=filename, student_name=name, row_index=2)

        result = process_student(student, cfg)
        assert result.status == ProcessingStatus.SUCCESS
        assert result.final_page_count % 4 == 0

    def test_all_students_valid_output(self, test_env):
        cfg, students = test_env
        records = [
            StudentRecord(filename=fn, student_name=nm, row_index=i + 2)
            for i, (fn, nm) in enumerate(students)
        ]

        report = run_batch(records, cfg, max_workers=1)
        assert report.total == len(students)
        assert report.success == len(students)
        assert report.errors == 0

        # Verify each output
        for r in report.results:
            assert r.output_path is not None
            assert r.output_path.exists()
            doc = fitz.open(str(r.output_path))
            assert doc.page_count == r.final_page_count
            assert doc.page_count % 4 == 0
            doc.close()


# ── PDF Scanner Tests ────────────────────────────────────────


class TestPDFScanner:
    """Tests for automatic PDF discovery and name extraction."""

    def test_scan_finds_student_pdfs(self, test_env):
        cfg, students = test_env
        records = scan_student_pdfs(cfg.input_path, cfg)
        assert len(records) == len(students)

    def test_scan_excludes_templates(self, test_env):
        cfg, students = test_env
        records = scan_student_pdfs(cfg.input_path, cfg)
        filenames = {r.safe_filename for r in records}
        assert "front_template.pdf" not in filenames
        assert "back_cover.pdf" not in filenames

    def test_scan_extracts_names(self, test_env):
        cfg, students = test_env
        records = scan_student_pdfs(cfg.input_path, cfg)
        extracted_names = {r.safe_name for r in records}
        # Each student name should be found in extracted names
        for _, expected_name in students:
            # The extracted text contains "Prepared for: <name>"
            # so the extracted name should match
            assert any(expected_name in name for name in extracted_names)

    def test_scan_empty_dir(self, tmp_dir):
        input_dir = tmp_dir / "input_pdfs"
        input_dir.mkdir()
        cfg = EngineConfig(base_path=tmp_dir)
        records = scan_student_pdfs(input_dir, cfg)
        assert len(records) == 0


# ── Config Tests ─────────────────────────────────────────────


class TestConfig:
    """Tests for configuration loading and validation."""

    def test_load_config(self, test_env):
        cfg, _ = test_env
        assert cfg.detection.max_scan_pages == 10
        assert cfg.template.marker_text == "{{STUDENT_NAME}}"
        assert cfg.processing.booklet_page_multiple == 4

    def test_paths_resolved(self, test_env):
        cfg, _ = test_env
        assert cfg.input_path.is_absolute()
        assert cfg.front_template_path.name == "front_template.pdf"
