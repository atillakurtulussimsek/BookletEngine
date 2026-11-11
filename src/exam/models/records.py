"""
Data models for processing results and student records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ProcessingStatus(Enum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class StudentRecord:
    """Single row from students.csv."""
    filename: str
    student_name: str
    row_index: int  # 1-based CSV row number for error reporting

    @property
    def safe_filename(self) -> str:
        """Return filename stripped of surrounding whitespace."""
        return self.filename.strip()

    @property
    def safe_name(self) -> str:
        """Return student name stripped of surrounding whitespace."""
        return self.student_name.strip()


@dataclass
class DetectionResult:
    """Result of first-page name detection."""
    pages_to_remove: list[int] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.pages_to_remove)


@dataclass
class ProcessingResult:
    """Result of processing a single student PDF."""
    student: StudentRecord
    status: ProcessingStatus
    output_path: Optional[Path] = None
    pages_removed: int = 0
    blank_pages_added: int = 0
    final_page_count: int = 0
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    details: list[str] = field(default_factory=list)


@dataclass
class BatchReport:
    """Aggregate report for entire processing run."""
    total: int = 0
    success: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[ProcessingResult] = field(default_factory=list)
    total_time_seconds: float = 0.0

    def add(self, result: ProcessingResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == ProcessingStatus.SUCCESS:
            self.success += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.skipped += 1
        else:
            self.errors += 1
