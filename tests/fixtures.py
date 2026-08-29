"""
Test fixtures and sample data generators.

Creates minimal but valid PDFs for testing the full pipeline
without requiring real student data.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF (modern import name)

# Locate a TrueType font that supports Turkish characters (ı, ğ, ş, etc.)
# Helvetica (built-in) lacks these; DejaVu Sans has full coverage.
_TURKISH_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _find_turkish_font() -> Optional[str]:
    """Find a system font supporting Turkish characters."""
    for p in _TURKISH_FONT_PATHS:
        if Path(p).exists():
            return p
    return None


_TURKISH_FONT = _find_turkish_font()


def create_sample_student_pdf(
    output_path: Path,
    student_name: str,
    num_content_pages: int = 7,
    include_name_on_page1: bool = False,
    include_name_on_page2: bool = False,
    name_starts_on_page: int = 3,
) -> None:
    """Generate a test student PDF with optional name in bottom-left.

    By default creates a realistic PDF with 2 cover pages (no name)
    followed by content pages that have the student name in the
    bottom-left region. The detection logic removes pages UNTIL
    the name is found.

    Args:
        output_path: Where to save the PDF.
        student_name: Name to embed in bottom-left region.
        num_content_pages: Total pages.
        include_name_on_page1: Put name on page 1's bottom-left.
        include_name_on_page2: Put name on page 2's bottom-left.
        name_starts_on_page: 1-based page number from which name appears
                             on all subsequent pages (default: 3).
                             Ignored if set to 0 or None.
    """
    doc = fitz.open()

    for page_idx in range(num_content_pages):
        page = doc.new_page(width=595, height=842)  # A4

        # Header
        header_rect = fitz.Rect(50, 50, 545, 100)
        page.insert_textbox(
            header_rect,
            f"Practice Exam — Page {page_idx + 1}",
            fontsize=16,
            align=fitz.TEXT_ALIGN_CENTER,
        )

        # Body content
        body_rect = fitz.Rect(50, 120, 545, 700)
        page.insert_textbox(
            body_rect,
            f"Question content for page {page_idx + 1}.\n"
            f"This is sample exam content that would normally contain\n"
            f"practice questions specific to the student.\n" * 5,
            fontsize=10,
        )

        # Bottom-left region — student name (for detection)
        # Determine if this page should have the name
        has_name = False
        if page_idx == 0 and include_name_on_page1:
            has_name = True
        elif page_idx == 1 and include_name_on_page2:
            has_name = True
        elif name_starts_on_page and (page_idx + 1) >= name_starts_on_page:
            has_name = True

        if has_name:
            name_rect = fitz.Rect(20, 750, 280, 820)  # bottom-left
            kwargs = {"fontsize": 9}
            if _TURKISH_FONT:
                kwargs["fontfile"] = _TURKISH_FONT
                kwargs["fontname"] = "dejavu"
            page.insert_textbox(
                name_rect,
                f"Prepared for: {student_name}",
                **kwargs,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_front_template(output_path: Path, with_marker: bool = True) -> None:
    """Generate a front template PDF with {{STUDENT_NAME}} marker.

    Args:
        output_path: Where to save front_template.pdf.
        with_marker: Include the text marker (False for fallback testing).
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title
    title_rect = fitz.Rect(50, 100, 545, 200)
    page.insert_textbox(
        title_rect,
        "Practice Exam Booklet",
        fontsize=28,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    # Subtitle
    sub_rect = fitz.Rect(50, 220, 545, 280)
    page.insert_textbox(
        sub_rect,
        "2025-2026 Academic Year",
        fontsize=16,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    # Student name marker
    if with_marker:
        marker_rect = fitz.Rect(150, 350, 450, 390)
        marker_kwargs = {"fontsize": 14, "align": fitz.TEXT_ALIGN_CENTER}
        if _TURKISH_FONT:
            marker_kwargs["fontfile"] = _TURKISH_FONT
            marker_kwargs["fontname"] = "dejavu"
        page.insert_textbox(
            marker_rect,
            "{{STUDENT_NAME}}",
            **marker_kwargs,
        )

    # School info
    info_rect = fitz.Rect(50, 700, 545, 780)
    page.insert_textbox(
        info_rect,
        "Example School — Education Department",
        fontsize=12,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_back_cover(output_path: Path) -> None:
    """Generate a simple back cover PDF (1 page)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    rect = fitz.Rect(50, 350, 545, 450)
    page.insert_textbox(
        rect,
        "End of Booklet\n© 2026 Example School",
        fontsize=14,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def create_sample_csv(output_path: Path, students: list[tuple[str, str]]) -> None:
    """Generate students.csv.

    Args:
        output_path: Where to save CSV.
        students: List of (filename, student_name) tuples.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "student_name"])
        for filename, name in students:
            writer.writerow([filename, name])


def setup_test_environment(base_dir: Path, num_students: int = 3) -> list[tuple[str, str]]:
    """Create a complete test environment with all required files.

    Args:
        base_dir: Root directory for the test setup.
        num_students: Number of test students to generate.

    Returns:
        List of (filename, student_name) tuples created.
    """
    input_dir = base_dir / "input_pdfs"
    input_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "output_pdfs").mkdir(parents=True, exist_ok=True)
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)

    # Turkish names for realistic testing
    test_students = [
        ("student_001.pdf", "Ahmet Yılmaz"),
        ("student_002.pdf", "Elif Öztürk"),
        ("student_003.pdf", "Mehmet Çelik"),
        ("student_004.pdf", "Ayşe Şahin"),
        ("student_005.pdf", "İbrahim Güneş"),
    ][:num_students]

    # Create student PDFs
    for filename, name in test_students:
        create_sample_student_pdf(input_dir / filename, name)

    # Create template files
    create_front_template(input_dir / "front_template.pdf")
    create_back_cover(input_dir / "back_cover.pdf")

    return test_students
