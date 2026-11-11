"""
Web job manager — zip upload → batch processing → result zip.

Two engines share this manager:
    exam    — Deneme kitapçığı (src.exam):   name from bottom-left region,
              cover pages removed, templates front_template.pdf / back_cover.pdf
    analyse — Analiz kitapçığı (src.analyse): name from "Ad Soyad" header table,
              all pages kept, templates front.pdf / back.pdf

Each job lives in its own directory under jobs/<jobId>/:
    upload.zip   — raw uploaded archive
    input/       — extracted student PDFs + templates
    output/      — generated booklets (deleted after zipping)
    logs/        — per-job logs
    result.zip   — final downloadable archive

Jobs run in a background thread; heavy PDF work is distributed to a
ProcessPoolExecutor exactly like the CLI engines.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.analyse.core import engine as analyseEngine
from src.analyse.models.config import load_config as loadAnalyseConfig
from src.analyse.utils.pdf_scanner import scan_student_pdfs as scanAnalysePdfs
from src.exam.core import engine as examEngine
from src.exam.models.config import load_config as loadExamConfig
from src.exam.utils.pdf_scanner import scan_student_pdfs as scanExamPdfs

logger = logging.getLogger("booklet_engine.web")

BASE_DIR = Path(__file__).resolve().parents[2]
JOBS_DIR = BASE_DIR / "jobs"
JOB_TTL_SECONDS = 2 * 60 * 60  # old job dirs are purged after 2 hours
UPLOAD_NAME = "upload.zip"
RESULT_NAME = "result.zip"

ENGINES: dict[str, dict] = {
    "exam": {
        "label": "Deneme kitapçığı",
        "configPath": BASE_DIR / "config.exam.json",
        "loadConfig": loadExamConfig,
        "scan": scanExamPdfs,
        "processWrapper": examEngine._process_wrapper,
        "dictToResult": examEngine._dict_to_result,
    },
    "analyse": {
        "label": "Analiz kitapçığı",
        "configPath": BASE_DIR / "config.analyse.json",
        "loadConfig": loadAnalyseConfig,
        "scan": scanAnalysePdfs,
        "processWrapper": analyseEngine._process_wrapper,
        "dictToResult": analyseEngine._dict_to_result,
    },
}


@dataclass
class Job:
    jobId: str
    mode: str = "exam"
    state: str = "uploaded"  # uploaded|extracting|scanning|processing|zipping|done|error
    total: int = 0
    done: int = 0
    errors: int = 0
    failed: list = field(default_factory=list)
    message: str = ""
    createdAt: float = field(default_factory=time.time)

    @property
    def jobDir(self) -> Path:
        return JOBS_DIR / self.jobId

    def toDict(self) -> dict:
        return {
            "jobId": self.jobId,
            "mode": self.mode,
            "state": self.state,
            "total": self.total,
            "done": self.done,
            "errors": self.errors,
            "failed": self.failed,
            "message": self.message,
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def createJob(mode: str) -> Job:
    """Register a new job and create its directory."""
    jobId = uuid.uuid4().hex[:12]
    job = Job(jobId=jobId, mode=mode)
    job.jobDir.mkdir(parents=True, exist_ok=True)
    with _lock:
        _jobs[jobId] = job
    return job


def getJob(jobId: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(jobId)


def startJob(jobId: str) -> None:
    """Run the job pipeline in a daemon thread."""
    thread = threading.Thread(target=_runJob, args=(jobId,), daemon=True)
    thread.start()


def cleanupOldJobs() -> None:
    """Delete job directories (and registry entries) older than the TTL."""
    now = time.time()
    if not JOBS_DIR.exists():
        return
    for jobDir in JOBS_DIR.iterdir():
        if not jobDir.is_dir():
            continue
        try:
            age = now - jobDir.stat().st_mtime
            job = getJob(jobDir.name)
            isRunning = job is not None and job.state not in ("done", "error")
            if age > JOB_TTL_SECONDS and not isRunning:
                shutil.rmtree(jobDir, ignore_errors=True)
                with _lock:
                    _jobs.pop(jobDir.name, None)
                logger.info(f"Purged old job {jobDir.name}")
        except OSError:
            continue


def _extractZip(job: Job) -> int:
    """Extract only PDF entries from the uploaded zip into input/.

    Entries are flattened to their basename (zip-slip safe) and
    macOS metadata is skipped. Returns the number of PDFs extracted.
    The uploaded zip is deleted afterwards to free disk space.
    """
    zipPath = job.jobDir / UPLOAD_NAME
    inputDir = job.jobDir / "input"
    inputDir.mkdir(exist_ok=True)

    count = 0
    with zipfile.ZipFile(zipPath) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if not name.lower().endswith(".pdf"):
                continue
            if name.startswith("._") or "__MACOSX" in info.filename:
                continue
            target = inputDir / name
            # Avoid silent overwrite on duplicate basenames
            stem, suffix = target.stem, target.suffix
            dupIndex = 1
            while target.exists():
                target = inputDir / f"{stem} ({dupIndex}){suffix}"
                dupIndex += 1
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
            count += 1

    zipPath.unlink(missing_ok=True)
    return count


def _buildJobConfig(job: Job, baseCfg: Any) -> Any:
    """Derive a per-job config rooted at the job directory."""
    cfg = baseCfg.model_copy(
        deep=True,
        update={
            "input_dir": "input",
            "output_dir": "output",
            "log_dir": "logs",
            # Absolute path wins in pathlib joins — fonts stay shared
            "font_dir": str(BASE_DIR / "fonts"),
        },
    )
    cfg.base_path = job.jobDir
    # Extracted copies are temporary — always delete to save disk
    cfg.processing.delete_source_pdf = True
    return cfg


def _copyTemplates(job: Job, cfg: Any, baseCfg: Any) -> None:
    """Ensure template PDFs exist in the job input dir.

    Templates inside the uploaded zip take precedence; otherwise the
    server's bundled templates are copied in.
    """
    for filename in (cfg.front_template_filename, cfg.back_cover_filename):
        target = cfg.input_path / filename
        if target.exists():
            continue
        source = baseCfg.input_path / filename
        if not source.exists():
            raise FileNotFoundError(f"Şablon bulunamadı: {source}")
        shutil.copy2(source, target)


def _zipResults(job: Job, cfg: Any) -> Path:
    """Zip all booklets into result.zip, deleting each PDF as it is added."""
    resultPath = job.jobDir / RESULT_NAME
    outputs = sorted(cfg.output_path.glob("*.pdf"))
    # PDFs are already compressed — ZIP_STORED is much faster
    with zipfile.ZipFile(resultPath, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for pdf in outputs:
            zf.write(pdf, arcname=pdf.name)
            pdf.unlink()
    return resultPath


def _runJob(jobId: str) -> None:
    job = getJob(jobId)
    if job is None:
        return
    engine = ENGINES[job.mode]

    try:
        baseCfg = engine["loadConfig"](engine["configPath"])

        job.state = "extracting"
        extracted = _extractZip(job)
        if extracted == 0:
            job.state = "error"
            job.message = "Zip içinde PDF bulunamadı."
            return

        cfg = _buildJobConfig(job, baseCfg)
        cfg.output_path.mkdir(parents=True, exist_ok=True)
        cfg.log_path.mkdir(parents=True, exist_ok=True)
        _copyTemplates(job, cfg, baseCfg)

        job.state = "scanning"
        students = engine["scan"](cfg.input_path, cfg)
        if not students:
            job.state = "error"
            job.message = "PDF'lerden öğrenci adı çıkarılamadı."
            return

        job.total = len(students)
        job.state = "processing"

        workItems = [(student, cfg) for student in students]
        with ProcessPoolExecutor(max_workers=cfg.processing.max_workers) as executor:
            futureMap = {
                executor.submit(engine["processWrapper"], item): item[0]
                for item in workItems
            }
            for future in as_completed(futureMap):
                student = futureMap[future]
                try:
                    result = engine["dictToResult"](future.result())
                    statusValue = result.status.value
                    errorMessage = result.error_message
                except Exception as e:  # worker crash
                    statusValue = "ERROR"
                    errorMessage = f"Worker crashed: {e}"
                    logger.exception(f"Worker crash for {student.safe_filename}")

                job.done += 1
                if statusValue != "SUCCESS":
                    job.errors += 1
                    job.failed.append(f"{student.safe_filename}: {errorMessage}")

        if job.errors == job.total:
            job.state = "error"
            job.message = "Hiçbir kitapçık oluşturulamadı."
            return

        job.state = "zipping"
        _zipResults(job, cfg)

        # Input copies are gone (delete_source_pdf) — drop the rest too
        shutil.rmtree(cfg.input_path, ignore_errors=True)
        shutil.rmtree(cfg.output_path, ignore_errors=True)

        job.state = "done"
        job.message = f"{job.total - job.errors}/{job.total} kitapçık hazır."
        logger.info(f"Job {jobId} ({job.mode}) done: {job.message}")

    except Exception as e:
        job.state = "error"
        job.message = f"{type(e).__name__}: {e}"
        logger.exception(f"Job {jobId} failed")
