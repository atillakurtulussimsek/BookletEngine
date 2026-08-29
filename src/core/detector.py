""" 
Cover page detection engine.

Uses PyMuPDF to extract text from a configurable bottom-left region
of each page, removing pages UNTIL the student name is found.

Logic:
    Pages at the beginning of a student PDF that do NOT contain the
    student's name in the bottom-left region are considered cover/intro
    pages (publisher covers, instruction pages, etc.) and are marked
    for removal. Scanning stops at the first page WHERE the student
    name IS found — that page and all subsequent pages are kept.

PDF Coordinate System Explanation:
    PDF uses a bottom-left origin coordinate system:
    - (0, 0) is bottom-left of the page
    - x increases rightward
    - y increases upward
    - Page dimensions given by page.rect: Rect(x0, y0, x1, y1)
      where (x0, y0) is top-left and (x1, y1) is bottom-right
      in PyMuPDF's coordinate system (top-left origin).

    PyMuPDF uses a TOP-LEFT origin (screen coordinates), so:
    - y=0 is the TOP of the page
    - y=page_height is the BOTTOM

    Our detection region (bottom-left) in PyMuPDF coords:
    - x: 0 to page_width * 0.5
    - y: page_height * 0.7 to page_height * 1.0

Region-Based Extraction — How It Works:
    1. Open PDF, access page object (no full-document load).
    2. Compute absolute pixel rect from ratio-based config.
    3. Call page.get_text("text", clip=rect) — PyMuPDF only decodes
       glyphs whose bounding boxes intersect the clip rectangle.
    4. This is O(glyphs_in_region) not O(glyphs_in_page).
    5. Compare extracted text against student name.
    6. If name NOT found → mark page for removal, continue.
    7. If name found → stop scanning, keep this page and all after.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf as fitz  # PyMuPDF (modern import name)

from src.models.config import DetectionConfig
from src.models.records import DetectionResult

logger = logging.getLogger("booklet_engine.detector")


def detect_removable_pages(
    pdf_path: Path,
    student_name: str,
    config: DetectionConfig,
) -> DetectionResult:
    """Scan pages from the start, removing until student name is found.

    Algorithm:
        For each page starting from page 1:
            1. Get page dimensions from mediabox.
            2. Compute clip rectangle from config ratios.
            3. Extract text within clip region only.
            4. Check if student_name appears in extracted text.
            5. If NOT found → mark page for removal, continue to next.
            6. If found → stop scanning (this is the first content page).

    This removes cover/intro pages that don't contain the student's
    name and preserves all pages starting from the first one that does.

    Args:
        pdf_path: Path to the student's original PDF.
        student_name: Name to search for.
        config: Detection configuration with region ratios.

    Returns:
        DetectionResult with list of 0-based page indices to remove.

    Raises:
        fitz.FileDataError: If PDF is corrupt.
    """
    result = DetectionResult()

    doc = fitz.open(str(pdf_path))
    try:
        total_pages = doc.page_count

        if total_pages < 2:
            msg = f"PDF has only {total_pages} page(s), minimum 2 required"
            logger.warning(f"{pdf_path.name}: {msg}")
            result.details.append(msg)
            return result

        max_scan = min(config.max_scan_pages, total_pages)
        compare_name = student_name if config.case_sensitive else student_name.lower()

        for page_idx in range(max_scan):
            page = doc[page_idx]
            page_rect = page.rect  # Rect(0, 0, width, height) in PyMuPDF coords

            # Compute clip rectangle from ratios
            # PyMuPDF: y=0 is top, y=height is bottom
            # "bottom-left" means: x from left edge, y toward bottom
            clip = fitz.Rect(
                page_rect.width * config.region_x0_ratio,   # x0
                page_rect.height * config.region_y0_ratio,  # y0 (70% down = near bottom)
                page_rect.width * config.region_x1_ratio,   # x1 (50% across = left half)
                page_rect.height * config.region_y1_ratio,  # y1 (100% = very bottom)
            )

            # Extract text ONLY within clip region
            text = page.get_text("text", clip=clip)
            compare_text = text if config.case_sensitive else text.lower()

            logger.debug(
                f"{pdf_path.name} page {page_idx + 1}: "
                f"region={clip}, extracted {len(text)} chars"
            )

            if compare_name in compare_text:
                # Student name found — this is a content page, stop scanning
                result.details.append(
                    f"Page {page_idx + 1}: name '{student_name}' found in bottom-left region, "
                    f"keeping this page and all subsequent pages"
                )
                logger.debug(
                    f"{pdf_path.name} page {page_idx + 1}: "
                    f"MATCH — name found, stopping scan (content starts here)"
                )
                break
            else:
                # No name found — this is a cover/intro page, mark for removal
                result.pages_to_remove.append(page_idx)
                result.details.append(
                    f"Page {page_idx + 1}: name not found in bottom-left region, marking for removal"
                )
                logger.debug(
                    f"{pdf_path.name} page {page_idx + 1}: "
                    f"NO MATCH — marking page for removal"
                )

    finally:
        doc.close()

    logger.info(
        f"{pdf_path.name}: {result.count} page(s) marked for removal "
        f"({result.pages_to_remove})"
    )
    return result


def validate_pdf(pdf_path: Path) -> tuple[bool, str]:
    """Quick corruption check by attempting to open and read page count.

    Args:
        pdf_path: Path to PDF file.

    Returns:
        Tuple of (is_valid, message).
    """
    try:
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        doc.close()
        if page_count == 0:
            return False, "PDF has 0 pages"
        return True, f"Valid PDF with {page_count} pages"
    except Exception as e:
        return False, f"Corrupt or unreadable PDF: {e}"
