"""
Booklet assembler — merges front template, student content, blank pages,
and back cover into a final PDF with page count divisible by 4.

How Blank Page Insertion Works Internally:
    The booklet printing process requires the total page count to be a
    multiple of 4 (each physical sheet = 4 printed pages in saddle-stitch
    or perfect-bound booklets).

    Algorithm:
        1. Count pages so far: front_template_pages + student_content_pages.
        2. Count pages in back_cover.pdf.
        3. Compute future_total = current_pages + back_cover_pages.
        4. If future_total % 4 != 0:
               blank_needed = 4 - (future_total % 4)
           Else:
               blank_needed = 0
        5. Create blank pages matching the student content page size.
        6. Insert blank pages AFTER student content, BEFORE back cover.
        7. Append back cover.
        8. Assert final page count % 4 == 0.

    Blank pages are generated via pikepdf by creating an empty page
    with the same MediaBox dimensions as the last content page.

Memory Efficiency — pikepdf Streaming:
    pikepdf is built on QPDF, a C++ library that uses a lazy-loading
    object model. Pages are not decoded into memory until accessed.
    When copying pages between PDFs, pikepdf passes object references
    rather than copying full page content streams. The final save()
    uses incremental writing with configurable linearization.

    This means a 500-page operation uses roughly:
    - ~10MB baseline for pikepdf/QPDF overhead
    - Per-page overhead of object references (~1KB each)
    - Actual page data stays in source files until final write
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pikepdf

from src.exam.models.config import EngineConfig
from src.exam.models.records import DetectionResult

logger = logging.getLogger("booklet_engine.assembler")


def _create_blank_page_pdf(width: float, height: float) -> bytes:
    """Create a minimal 1-page PDF with given dimensions.

    Uses pikepdf's add_blank_page which creates a proper Page object
    with the correct MediaBox. More memory-efficient than ReportLab
    for blank pages.

    Args:
        width: Page width in PDF points (1 point = 1/72 inch).
        height: Page height in PDF points.

    Returns:
        PDF bytes containing a single blank page.
    """
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(width, height))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def assemble_booklet(
    student_pdf_path: Path,
    front_template_bytes: bytes,
    detection: DetectionResult,
    config: EngineConfig,
    output_path: Path,
) -> tuple[int, int, int]:
    """Assemble final booklet PDF for one student.

    Pipeline:
        1. Open personalized front template (from bytes).
        2. Open student PDF, skip detected pages.
        3. Copy remaining student pages.
        4. Compute blank pages needed for mod-4.
        5. Insert blank pages.
        6. Append back cover.
        7. Save with compression.

    Args:
        student_pdf_path: Path to original student PDF.
        front_template_bytes: Pre-processed front page PDF bytes.
        detection: Which pages (0-based) to remove from student PDF.
        config: Full engine configuration.
        output_path: Where to write the final booklet PDF.

    Returns:
        Tuple of (pages_removed, blank_pages_added, final_page_count).

    Raises:
        pikepdf.PdfError: If a source PDF is corrupt.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Open all source PDFs
    output_pdf = pikepdf.Pdf.new()
    front_pdf = pikepdf.open(io.BytesIO(front_template_bytes))
    student_pdf = pikepdf.open(str(student_pdf_path))
    back_pdf = pikepdf.open(str(config.back_cover_path))

    try:
        # --- Step 1: Insert front template pages ---
        for page in front_pdf.pages:
            output_pdf.pages.append(page)
        front_count = len(front_pdf.pages)
        logger.debug(f"Added {front_count} front template page(s)")

        # --- Step 2: Copy student pages, skipping detected ones ---
        pages_removed = 0
        remove_set = set(detection.pages_to_remove)
        student_pages_added = 0

        for idx, page in enumerate(student_pdf.pages):
            if idx in remove_set:
                pages_removed += 1
                logger.debug(f"Skipped student page {idx + 1} (name detected)")
                continue
            output_pdf.pages.append(page)
            student_pages_added += 1

        logger.debug(
            f"Added {student_pages_added} student page(s), "
            f"removed {pages_removed}"
        )

        # --- Step 3: Compute blank pages needed ---
        current_pages = len(output_pdf.pages)
        back_cover_pages = len(back_pdf.pages)
        future_total = current_pages + back_cover_pages
        booklet_mod = config.processing.booklet_page_multiple

        if future_total % booklet_mod != 0:
            blank_needed = booklet_mod - (future_total % booklet_mod)
        else:
            blank_needed = 0

        logger.debug(
            f"Pages so far: {current_pages}, back cover: {back_cover_pages}, "
            f"future total: {future_total}, blanks needed: {blank_needed}"
        )

        # --- Step 4: Insert blank pages ---
        if blank_needed > 0:
            # Match page size to last content page
            last_page = output_pdf.pages[-1]
            media_box = last_page.get("/MediaBox", pikepdf.Array([0, 0, 595, 842]))
            page_w = float(media_box[2]) - float(media_box[0])
            page_h = float(media_box[3]) - float(media_box[1])

            blank_bytes = _create_blank_page_pdf(page_w, page_h)
            blank_pdf = pikepdf.open(io.BytesIO(blank_bytes))

            for _ in range(blank_needed):
                output_pdf.pages.append(blank_pdf.pages[0])

            logger.debug(f"Inserted {blank_needed} blank page(s)")

        # --- Step 5: Append back cover ---
        for page in back_pdf.pages:
            output_pdf.pages.append(page)
        logger.debug(f"Added {back_cover_pages} back cover page(s)")

        # --- Step 6: Final validation ---
        final_count = len(output_pdf.pages)
        assert final_count % booklet_mod == 0, (
            f"Final page count {final_count} is not divisible by {booklet_mod}!"
        )

        # --- Step 7: Save with compression ---
        output_pdf.save(
            str(output_path),
            linearize=True,         # Optimize for web/fast viewing
            compress_streams=True,   # Deflate content streams
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )

        logger.info(
            f"Saved booklet: {output_path.name} "
            f"({final_count} pages, {pages_removed} removed, "
            f"{blank_needed} blanks added)"
        )

        return pages_removed, blank_needed, final_count

    finally:
        front_pdf.close()
        student_pdf.close()
        back_pdf.close()
        output_pdf.close()
