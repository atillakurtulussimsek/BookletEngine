FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.exam.json config.analyse.json ./
COPY src/ src/
COPY fonts/ fonts/
COPY input_pdfs/front_template.pdf input_pdfs/back_cover.pdf input_pdfs/front.pdf input_pdfs/back.pdf input_pdfs/

# Jobs live on a volume in production (Dokploy: mount /app/jobs)
RUN mkdir -p jobs logs

EXPOSE 8000

CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
