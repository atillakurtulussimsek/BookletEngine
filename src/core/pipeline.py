"""
Pipeline orchestrator — processes a single student PDF end-to-end.

This module is the unit of parallelism: each student is processed
by one call to `process_student()`, which can run in a separate
process via ProcessPoolExecutor.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from src.core.assembler import assemble_booklet
from src.core.detector import detect_removable_pages, validate_pdf
from src.core.template_processor import prepare_front_template
from src.models.config import EngineConfig
from src.models.records import (
    ProcessingResult,
    ProcessingStatus,
    StudentRecord,
)

logger = logging.getLogger("booklet_engine.pipeline")


def process_student(
    student: StudentRecord,
    config: EngineConfig,
) -> ProcessingResult:
    """Full processing pipeline for one student.

    Steps:
        1. Validate input PDF exists and is not corrupt.
        2. Detect removable cover pages (max 2).
        3. Prepare personalized front template.
        4. Assemble booklet with blank page padding.
        5. Record metrics and return result.

    This function is designed to be called from a process pool.
    It catches all exceptions and returns them as error results
    rather than propagating — no student failure crashes the batch.

    Args:
        student: Student record from CSV.
        config: Engine configuration (serializable across processes).

    Returns:
        ProcessingResult with status, metrics, and any error info.
    """
    start_time = time.perf_counter()

    result = ProcessingResult(student=student, status=ProcessingStatus.ERROR)

    try:
        # --- Step 1: Locate and validate input PDF ---
        pdf_path = config.input_path / student.safe_filename
        if not pdf_path.exists():
            result.status = ProcessingStatus.SKIPPED
            result.error_message = f"Input PDF not found: {pdf_path}"
            result.details.append(result.error_message)
            logger.warning(result.error_message)
            return result

        is_valid, msg = validate_pdf(pdf_path)
        if not is_valid:
            result.status = ProcessingStatus.ERROR
            result.error_message = f"Invalid PDF: {msg}"
            result.details.append(result.error_message)
            logger.error(result.error_message)
            return result

        # --- Step 2: Detect removable pages ---
        detection = detect_removable_pages(
            pdf_path=pdf_path,
            student_name=student.safe_name,
            config=config.detection,
        )
        result.details.extend(detection.details)

        # --- Step 3: Prepare front template ---
        front_bytes = prepare_front_template(
            template_path=config.front_template_path,
            student_name=student.safe_name,
            config=config.template,
            font_dir=config.font_path,
        )

        # --- Step 4: Assemble booklet ---
        output_filename = f"booklet_{student.safe_filename}"
        output_path = config.output_path / output_filename

        pages_removed, blank_added, final_count = assemble_booklet(
            student_pdf_path=pdf_path,
            front_template_bytes=front_bytes,
            detection=detection,
            config=config,
            output_path=output_path,
        )

        # --- Step 5: Record success ---
        result.status = ProcessingStatus.SUCCESS
        result.output_path = output_path
        result.pages_removed = pages_removed
        result.blank_pages_added = blank_added
        result.final_page_count = final_count

        logger.info(
            f"[OK] {student.safe_filename} → {output_filename} "
            f"({final_count} pages)"
        )

        # --- Step 6: Delete source PDF ---
        if config.processing.delete_source_pdf:
            try:
                pdf_path.unlink()
                logger.info(f"Deleted input PDF: {pdf_path.name}")
                result.details.append(f"Input PDF deleted: {pdf_path.name}")
            except OSError as e:
                logger.warning(f"Could not delete input PDF {pdf_path.name}: {e}")
                result.details.append(f"Warning: could not delete input PDF: {e}")

    except Exception as e:
        result.status = ProcessingStatus.ERROR
        result.error_message = f"{type(e).__name__}: {e}"
        result.details.append(result.error_message)
        logger.exception(f"[FAIL] {student.safe_filename}: {e}")

    finally:
        elapsed = (time.perf_counter() - start_time) * 1000
        result.processing_time_ms = elapsed

    return result
