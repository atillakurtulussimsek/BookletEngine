"""
PDF scanner — discovers student PDFs and extracts names from content.

Replaces CSV-based student discovery by automatically scanning the input
directory and extracting student names from the bottom-left region of
each PDF.

How It Works:
    1. List all .pdf files in the input directory.
    2. Exclude configured template files (front_template, back_cover).
    3. For each remaining PDF, sample multiple pages with PyMuPDF.
    4. Extract the first line of text from the bottom-left region of
       each sampled page.
    5. The student name is the first line that appears most frequently
       across sampled pages — this eliminates cover page noise.
    6. Optionally strip a configurable prefix (e.g., "Prepared for:").
    7. Return the cleaned text as the student name.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF (modern import name)

from src.models.config import DetectionConfig
from src.models.records import StudentRecord

logger = logging.getLogger("booklet_engine.scanner")


def _extract_first_line(text: str, config: DetectionConfig) -> Optional[str]:
    """Extract student name from region text, stripping prefix if configured.

    Args:
        text: Raw text from the bottom-left region.
        config: Detection configuration with optional name_prefix.

    Returns:
        Cleaned first line, or None if empty.
    """
    if not text.strip():
        return None

    # Strip configurable prefix (e.g., "Prepared for:")
    if config.name_prefix:
        prefix_lower = config.name_prefix.lower()
        for line in text.splitlines():
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if prefix_lower in line_lower:
                idx = line_lower.index(prefix_lower) + len(config.name_prefix)
                name = line_stripped[idx:].strip()
                if name:
                    return name

    # No prefix configured or prefix not found — use first non-empty line
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[0] if lines else None


def _extract_student_name(
    pdf_path: Path,
    config: DetectionConfig,
) -> Optional[str]:
    """Extract student name from the bottom-left region of the PDF.

    Samples multiple pages across the document and finds the most
    frequently occurring first line in the bottom-left region.
    This correctly identifies the student name even when cover pages
    have different text in the same region.

    Algorithm:
        1. Sample pages from across the document (skip first 2, then
           sample evenly distributed pages up to max_scan_pages).
        2. For each page, extract text from the bottom-left region.
        3. Collect the first line from each page's region text.
        4. The most common first line across sampled pages is the
           student name (content pages vastly outnumber cover pages).

    Args:
        pdf_path: Path to the student PDF.
        config: Detection configuration with region ratios and name_prefix.

    Returns:
        Extracted student name, or None if not found.
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.warning(f"{pdf_path.name}: cannot open PDF: {e}")
        return None

    try:
        total_pages = doc.page_count
        if total_pages == 0:
            logger.warning(f"{pdf_path.name}: PDF has 0 pages")
            return None

        # Build list of pages to sample:
        # - Skip first 2 pages (likely covers) if possible
        # - Sample up to max_scan_pages evenly across the rest
        if total_pages <= 3:
            # Small PDF — sample all pages
            sample_indices = list(range(total_pages))
        else:
            # Start from page 3 (index 2), sample evenly
            content_start = 2
            content_range = total_pages - content_start
            num_samples = min(config.max_scan_pages, content_range)
            if num_samples <= 0:
                sample_indices = [0, 1]
            else:
                step = max(1, content_range // num_samples)
                sample_indices = [
                    content_start + i * step
                    for i in range(num_samples)
                    if content_start + i * step < total_pages
                ]

        # Extract first lines from sampled pages
        first_lines: list[str] = []
        for page_idx in sample_indices:
            page = doc[page_idx]
            clip = fitz.Rect(
                page.rect.width * config.region_x0_ratio,
                page.rect.height * config.region_y0_ratio,
                page.rect.width * config.region_x1_ratio,
                page.rect.height * config.region_y1_ratio,
            )

            text = page.get_text("text", clip=clip).strip()
            first_line = _extract_first_line(text, config)
            if first_line:
                first_lines.append(first_line)

        if not first_lines:
            logger.warning(f"{pdf_path.name}: no text found in name region on any sampled page")
            return None

        # Find the most common first line — that's the student name
        counter = Counter(first_lines)
        name, count = counter.most_common(1)[0]

        logger.debug(
            f"{pdf_path.name}: extracted name '{name}' "
            f"(found on {count}/{len(first_lines)} sampled pages)"
        )
        return name

    finally:
        doc.close()


def scan_student_pdfs(
    input_dir: Path,
    config: "EngineConfig",  # noqa: F821 — forward ref to avoid circular import
) -> list[StudentRecord]:
    """Discover all student PDFs in input directory and extract names.

    Scans input_dir for .pdf files, excluding the front template and
    back cover files. For each PDF, extracts the student name from
    the bottom-left region of the first page.

    Args:
        input_dir: Directory containing student PDFs.
        config: Engine configuration.

    Returns:
        List of StudentRecord objects with extracted names.
    """
    excluded = {
        config.front_template_filename.lower(),
        config.back_cover_filename.lower(),
    }

    # Find all PDF files, excluding template files
    pdf_files = sorted(
        f for f in input_dir.glob("*.pdf")
        if f.name.lower() not in excluded
    )

    if not pdf_files:
        logger.warning(f"No student PDFs found in {input_dir}")
        return []

    logger.info(f"Found {len(pdf_files)} PDF file(s) in {input_dir}")

    records: list[StudentRecord] = []
    for idx, pdf_path in enumerate(pdf_files, start=1):
        name = _extract_student_name(pdf_path, config.detection)
        if name:
            records.append(StudentRecord(
                filename=pdf_path.name,
                student_name=name,
                row_index=idx,
            ))
            logger.debug(f"  {pdf_path.name} → {name}")
        else:
            logger.warning(
                f"Could not extract student name from {pdf_path.name}, skipping"
            )

    logger.info(f"Extracted {len(records)} student record(s) from PDFs")
    return records
