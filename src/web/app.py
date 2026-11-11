"""
FastAPI web uygulaması — zip yükle, kitapçıkları oluştur, sonucu indir.

Çalıştırma:
    uvicorn src.web.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.web import jobs

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Booklet Engine Web", version="1.0.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
CHUNK_SIZE = 8 * 1024 * 1024


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.post("/api/jobs")
async def uploadZip(file: UploadFile = File(...), mode: str = Form("exam")) -> dict:
    jobs.cleanupOldJobs()

    if mode not in jobs.ENGINES:
        raise HTTPException(status_code=400, detail="Geçersiz kitapçık türü.")
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Lütfen .zip dosyası yükleyin.")

    job = jobs.createJob(mode)
    zipPath = job.jobDir / jobs.UPLOAD_NAME
    try:
        with open(zipPath, "wb") as dst:
            while chunk := await file.read(CHUNK_SIZE):
                dst.write(chunk)
    except OSError as e:
        job.state = "error"
        job.message = f"Yükleme yazılamadı (disk dolu olabilir): {e}"
        raise HTTPException(status_code=507, detail=job.message)

    jobs.startJob(job.jobId)
    return {"jobId": job.jobId}


@app.get("/api/jobs/{jobId}")
async def jobStatus(jobId: str) -> dict:
    job = jobs.getJob(jobId)
    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    return job.toDict()


@app.get("/api/jobs/{jobId}/download")
async def downloadResult(jobId: str) -> FileResponse:
    job = jobs.getJob(jobId)
    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    if job.state != "done":
        raise HTTPException(status_code=409, detail="İş henüz tamamlanmadı.")
    resultPath = job.jobDir / jobs.RESULT_NAME
    if not resultPath.exists():
        raise HTTPException(status_code=410, detail="Sonuç dosyası silinmiş.")
    return FileResponse(
        resultPath,
        media_type="application/zip",
        filename="kitapciklar.zip",
    )
