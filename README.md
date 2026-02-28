# Booklet Engine — Customized Practice Exam Booklet Creation Tool

> **EN** | Production-grade PDF processing system for bulk-creating personalized student exam booklets ready for saddle-stitch or perfect-bound printing.
>
> **TR** | Öğrencilere özel sınav kitapçıklarını toplu olarak oluşturmak için üretim kalitesinde PDF işleme sistemi.

---

## Table of Contents / İçindekiler

- [Features / Özellikler](#features--özellikler)
- [Architecture / Mimari](#architecture--mimari)
- [Prerequisites / Gereksinimler](#prerequisites--gereksinimler)
- [Installation / Kurulum](#installation--kurulum)
- [Project Structure / Proje Yapısı](#project-structure--proje-yapısı)
- [Configuration / Yapılandırma](#configuration--yapılandırma)
- [Usage / Kullanım](#usage--kullanım)
- [How It Works / Nasıl Çalışır](#how-it-works--nasıl-çalışır)
- [Testing / Test](#testing--test)
- [Troubleshooting / Sorun Giderme](#troubleshooting--sorun-giderme)
- [Scaling / Ölçeklendirme](#scaling--ölçeklendirme)
- [License / Lisans](#license--lisans)

---

## Features / Özellikler

**EN:**
- **Automatic student discovery** — Scans input directory for PDF files, no CSV required
- **Name extraction from PDF** — Reads the student name from the bottom-left region of each PDF's first page
- **Personalized front cover** — Detects `{{STUDENT_NAME}}` marker in the template and replaces it with the student's name
- **Smart cover page removal** — Detects and removes existing cover pages containing the student's name
- **Booklet-ready output** — Automatically pads with blank pages to ensure total page count is a multiple of 4
- **Parallel processing** — Uses Python's ProcessPoolExecutor for multi-core batch processing
- **Auto-cleanup** — Optionally deletes source PDFs after successful processing
- **Rich console output** — Progress bars, colored status, and detailed reporting
- **Full Turkish character support** — DejaVu Sans font with complete UTF-8 coverage (ç, ğ, ı, ö, ş, ü, İ, Ş...)

**TR:**
- **Otomatik öğrenci keşfi** — Giriş klasöründeki PDF dosyalarını tarar, CSV dosyasına gerek yoktur
- **PDF'den isim çıkarma** — Her PDF'in ilk sayfasının sol alt bölgesinden öğrenci adını okur
- **Kişiselleştirilmiş ön kapak** — Şablondaki `{{STUDENT_NAME}}` işaretçisini bulur ve öğrenci adıyla değiştirir
- **Akıllı kapak sayfası kaldırma** — Öğrenci adını içeren mevcut kapak sayfalarını tespit edip kaldırır
- **Kitapçık uyumlu çıktı** — Toplam sayfa sayısının 4'ün katı olması için boş sayfalar ekler
- **Paralel işlem** — ProcessPoolExecutor ile çok çekirdekli toplu işlem
- **Otomatik temizlik** — Başarılı işlem sonrası kaynak PDF'leri isteğe bağlı olarak siler
- **Zengin konsol çıktısı** — İlerleme çubukları, renkli durum bilgisi ve detaylı raporlama
- **Tam Türkçe karakter desteği** — DejaVu Sans fontu ile UTF-8 (ç, ğ, ı, ö, ş, ü, İ, Ş...)

---

## Architecture / Mimari

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (Click)                          │
│  run │ validate │ --single │ --dry-run │ --workers N        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Batch Engine                                │
│  ProcessPoolExecutor  │  Rich Progress  │  Report CSV        │
└────────────────────────┬────────────────────────────────────┘
                         │  (per student)
┌────────────────────────▼────────────────────────────────────┐
│                   Pipeline                                   │
│  scan → validate → detect → template → assemble → cleanup    │
└──┬──────────┬──────────┬───────────┬──────────┬─────────────┘
   │          │          │           │          │
   ▼          ▼          ▼           ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌───────┐
│Scan- │ │Detect- │ │Template│ │Assembler │ │Delete │
│ner   │ │  or    │ │Process-│ │(pikepdf) │ │Source │
│(fitz)│ │(fitz)  │ │  or    │ │          │ │ PDF   │
│      │ │        │ │(report-│ │blank pg  │ │       │
│auto  │ │region  │ │ lab +  │ │mod-4 pad │ │       │
│disc. │ │extract │ │ fitz)  │ │linearize │ │       │
└──────┘ └────────┘ └────────┘ └──────────┘ └───────┘
```

### Library Choices / Kütüphane Tercihleri

| Library | Role / Rol | Why / Neden |
|---------|-----------|-------------|
| **PyMuPDF (fitz)** | Text extraction, detection | Fastest Python PDF lib — C-backed, region-clipped extraction |
| **pikepdf** | Page manipulation, assembly | QPDF-based, lazy-loading, streaming save |
| **ReportLab** | Text overlay generation | Full Unicode/TTF embedding, precise coordinates |
| **Pydantic** | Config validation | Type-safe config with clear errors |
| **Rich** | Console output | Beautiful progress bars and tables |
| **Click** | CLI framework | Declarative CLI with type validation |

---

## Prerequisites / Gereksinimler

**EN:**
- Python 3.10 or later
- `pip` (Python package manager)
- `git` (to clone the repository)
- A TrueType font with Turkish character support (DejaVu Sans recommended)

**TR:**
- Python 3.10 veya üzeri
- `pip` (Python paket yöneticisi)
- `git` (depoyu klonlamak için)
- Türkçe karakter destekli bir TrueType fontu (DejaVu Sans önerilir)

### Check your Python version / Python sürümünüzü kontrol edin

```bash
python3 --version   # Should be 3.10+
```

---

## Installation / Kurulum

### EN: Install on a New Machine

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/CustomizedPracticeExamBookletCreationTool.git
cd CustomizedPracticeExamBookletCreationTool

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate the virtual environment
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows (Command Prompt)
# venv\Scripts\Activate.ps1       # Windows (PowerShell)

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Install Turkish font
# Linux (Ubuntu/Debian):
sudo apt install fonts-dejavu-core
# Or manually copy DejaVuSans.ttf into the fonts/ directory

# 6. Verify installation
python -m src.cli --version
```

### TR: Yeni Bir Bilgisayara Kurulum

```bash
# 1. Depoyu klonlayın
git clone https://github.com/atillakurtulussimsek/CustomizedPracticeExamBookletCreationTool.git
cd CustomizedPracticeExamBookletCreationTool

# 2. Sanal ortam oluşturun
python3 -m venv venv

# 3. Sanal ortamı etkinleştirin
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows (Komut İstemi)
# venv\Scripts\Activate.ps1       # Windows (PowerShell)

# 4. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 5. (İsteğe bağlı) Türkçe font yükleyin
# Linux (Ubuntu/Debian):
sudo apt install fonts-dejavu-core
# Veya DejaVuSans.ttf dosyasını fonts/ klasörüne kopyalayın

# 6. Kurulumu doğrulayın
python -m src.cli --version
```

---

## Project Structure / Proje Yapısı

```
├── config.json                 # Configuration / Yapılandırma
├── pyproject.toml              # Package metadata / Paket bilgisi
├── requirements.txt            # Dependencies / Bağımlılıklar
├── fonts/                      # TTF fonts (DejaVuSans)
├── input_pdfs/                 # Input directory / Giriş klasörü
│   ├── front_template.pdf      # Front cover template / Ön kapak şablonu
│   ├── back_cover.pdf          # Back cover / Arka kapak
│   └── *.pdf                   # Student PDFs / Öğrenci PDF'leri
├── output_pdfs/                # Generated booklets / Üretilen kitapçıklar
├── logs/                       # Log files + report CSVs
├── src/
│   ├── cli.py                  # CLI entry point
│   ├── core/
│   │   ├── detector.py         # First-page name detection
│   │   ├── template_processor.py # Marker detection + name overlay
│   │   ├── assembler.py        # Booklet assembly + blank pages
│   │   ├── pipeline.py         # Single-student orchestrator
│   │   └── engine.py           # Batch engine with parallelism
│   ├── models/
│   │   ├── config.py           # Pydantic config models
│   │   └── records.py          # Data classes for results
│   └── utils/
│       ├── logging.py          # Dual logging (Rich + file)
│       ├── pdf_scanner.py      # Auto-discover PDFs + extract names
│       └── font_manager.py     # TTF discovery + registration
└── tests/
    ├── fixtures.py             # Test PDF generators
    ├── generate_test_data.py   # CLI for test data
    └── test_engine.py          # Integration tests
```

---

## Configuration / Yapılandırma

### EN: config.json Reference

All settings are in `config.json` at the project root:

```jsonc
{
    // Directory paths (relative to project root)
    "input_dir": "input_pdfs",           // Where student PDFs are placed
    "output_dir": "output_pdfs",         // Where booklets are written
    "log_dir": "logs",                   // Log files and reports
    "font_dir": "fonts",                 // Custom font directory

    // Template files (inside input_dir)
    "front_template_filename": "front_template.pdf",  // Must contain {{STUDENT_NAME}}
    "back_cover_filename": "back_cover.pdf",           // Added as last page(s)

    "detection": {
        "max_scan_pages": 2,             // Max pages to scan for student name (1 or 2)
        "region_x0_ratio": 0.0,          // Left edge of scan region (0.0 = left)
        "region_y0_ratio": 0.7,          // Top of scan region (0.7 = 70% down the page)
        "region_x1_ratio": 0.5,          // Right edge of scan region (0.5 = middle)
        "region_y1_ratio": 1.0,          // Bottom of scan region (1.0 = bottom)
        "case_sensitive": false,          // Case-sensitive name matching
        "name_prefix": ""                // Prefix to strip (e.g. "Prepared for:")
    },

    "template": {
        "marker_text": "{{STUDENT_NAME}}",  // Text to find and replace in template
        "fallback_x": 200,                  // X position if marker not found
        "fallback_y": 400,                  // Y position if marker not found
        "font_name": "DejaVuSans",          // Font for student name
        "font_size": 14,                    // Font size in points
        "font_color_r": 0,                  // Red channel (0.0-1.0)
        "font_color_g": 0,                  // Green channel
        "font_color_b": 0                   // Blue channel (0=black)
    },

    "processing": {
        "max_workers": 4,                // Parallel worker count
        "booklet_page_multiple": 4,      // Page count must be multiple of this
        "stream_buffer_size_mb": 64,     // Memory buffer for PDF streams
        "delete_source_pdf": true        // Delete input PDF after successful processing
    }
}
```

### TR: config.json Referansı

Tüm ayarlar proje kök dizinindeki `config.json` dosyasındadır:

| Alan | Açıklama | Varsayılan |
|------|----------|------------|
| `input_dir` | Öğrenci PDF'lerinin bulunduğu klasör | `input_pdfs` |
| `output_dir` | Kitapçıkların yazılacağı klasör | `output_pdfs` |
| `log_dir` | Log dosyaları ve raporlar | `logs` |
| `font_dir` | Özel font klasörü | `fonts` |
| `front_template_filename` | Ön kapak şablon dosyası (`{{STUDENT_NAME}}` içermeli) | `front_template.pdf` |
| `back_cover_filename` | Arka kapak dosyası | `back_cover.pdf` |
| `detection.name_prefix` | İsim alanında çıkarılacak ön ek (ör: `"Hazırlayan:"`) | `""` (boş) |
| `detection.case_sensitive` | Büyük/küçük harf duyarlı eşleştirme | `false` |
| `processing.max_workers` | Paralel işlem sayısı | `4` |
| `processing.delete_source_pdf` | Başarılı işlem sonrası kaynak PDF'i sil | `true` |

---

## Usage / Kullanım

### EN: Preparing Your Files

1. **Place student PDFs** into the `input_pdfs/` directory. Each PDF must have the student's name printed in the bottom-left region of its first page.

2. **Prepare `front_template.pdf`** — a single-page PDF with the text `{{STUDENT_NAME}}` where you want each student's name to appear. Place it in `input_pdfs/`.

3. **Prepare `back_cover.pdf`** — the back cover page(s). Place it in `input_pdfs/`.

4. **(Optional)** If the student name lines contain a prefix like `"Prepared for: Ahmet Yılmaz"`, set `detection.name_prefix` to `"Prepared for:"` in `config.json` so only the name is extracted.

### TR: Dosyaları Hazırlama

1. **Öğrenci PDF'lerini** `input_pdfs/` klasörüne koyun. Her PDF'in ilk sayfasının sol alt bölgesinde öğrenci adı yazılı olmalıdır.

2. **`front_template.pdf` hazırlayın** — öğrenci adının görünmesini istediğiniz yere `{{STUDENT_NAME}}` yazılmış tek sayfalık bir PDF. `input_pdfs/` klasörüne koyun.

3. **`back_cover.pdf` hazırlayın** — arka kapak sayfası. `input_pdfs/` klasörüne koyun.

4. **(İsteğe bağlı)** Öğrenci adı satırları `"Hazırlayan: Ahmet Yılmaz"` gibi bir ön ek içeriyorsa, `config.json` dosyasında `detection.name_prefix` alanını `"Hazırlayan:"` olarak ayarlayın.

### Running the Tool / Aracı Çalıştırma

```bash
# Activate virtual environment first / Önce sanal ortamı etkinleştirin
source venv/bin/activate

# ── Full batch processing / Tam toplu işlem ──
python -m src.cli run --config config.json

# ── With 8 parallel workers / 8 paralel işçi ile ──
python -m src.cli run -c config.json -w 8

# ── Single file (for testing) / Tek dosya (test için) ──
python -m src.cli run -c config.json --single student_001.pdf

# ── Dry run — validate without processing / Kuru çalıştırma — işlem yapmadan doğrulama ──
python -m src.cli run -c config.json --dry-run

# ── Debug mode — verbose output / Hata ayıklama — ayrıntılı çıktı ──
python -m src.cli run -c config.json --verbose

# ── Validate inputs only / Sadece girdileri doğrula ──
python -m src.cli validate -c config.json
```

### CLI Options / CLI Seçenekleri

| Option / Seçenek | Short | Description / Açıklama |
|---|---|---|
| `--config` | `-c` | Path to config.json / config.json yolu |
| `--workers` | `-w` | Override parallel worker count / Paralel işçi sayısını geçersiz kıl |
| `--verbose` | `-v` | Enable debug output / Hata ayıklama çıktısını etkinleştir |
| `--single` | `-s` | Process only one file / Sadece bir dosya işle |
| `--dry-run` | — | Validate without processing / İşlem yapmadan doğrula |

### Example Output / Örnek Çıktı

```
Processing booklets ━━━━━━━━━━━━━━━━━━━━━━━━━━ 500/500 0:02:34 0:00:00

┌──────────────────────────────────────┐
│  Booklet Engine — Processing Report  │
├──────────────────┬───────────────────┤
│ Metric           │             Value │
├──────────────────┼───────────────────┤
│ Total Students   │               500 │
│ Success          │               498 │
│ Skipped          │                 1 │
│ Errors           │                 1 │
│ Total Time       │           154.23s │
│ Avg per PDF      │             308ms │
└──────────────────┴───────────────────┘
```

---

## How It Works / Nasıl Çalışır

### EN: Processing Pipeline

For each student PDF the engine runs these steps:

1. **Scan** — Discover all `.pdf` files in `input_pdfs/`, excluding `front_template.pdf` and `back_cover.pdf`.
2. **Extract Name** — Open each PDF's first page with PyMuPDF, read text from the bottom-left region, strip the optional prefix, and use it as the student name.
3. **Validate** — Check the PDF can be opened and has at least 2 pages.
4. **Detect** — Search pages 1–2 for the student name in the bottom-left region. Matching pages are marked for removal (they are old cover pages).
5. **Template** — Find `{{STUDENT_NAME}}` in `front_template.pdf`, draw a white rectangle over it, and render the student's name at the same coordinates using ReportLab.
6. **Assemble** — Combine the personalized front cover + remaining student content pages + blank pages (for mod-4 alignment) + back cover into one PDF using pikepdf.
7. **Cleanup** — If `delete_source_pdf` is `true`, the original student PDF is deleted after successful processing.

### TR: İşlem Hattı

Her öğrenci PDF'i için motor şu adımları çalıştırır:

1. **Tarama** — `input_pdfs/` içindeki tüm `.pdf` dosyalarını keşfeder, `front_template.pdf` ve `back_cover.pdf` hariç tutulur.
2. **İsim Çıkarma** — Her PDF'in ilk sayfası PyMuPDF ile açılır, sol alt bölgeden metin okunur, isteğe bağlı ön ek çıkarılır ve öğrenci adı olarak kullanılır.
3. **Doğrulama** — PDF'in açılabildiği ve en az 2 sayfası olduğu kontrol edilir.
4. **Tespit** — İlk 1-2 sayfada öğrenci adı sol alt bölgede aranır. Eşleşen sayfalar kaldırılmak üzere işaretlenir (eski kapak sayfalarıdır).
5. **Şablon** — `front_template.pdf` içinde `{{STUDENT_NAME}}` bulunur, üzerine beyaz dikdörtgen çizilir ve aynı koordinatlara ReportLab ile öğrenci adı yazılır.
6. **Birleştirme** — Kişiselleştirilmiş ön kapak + kalan öğrenci içerik sayfaları + boş sayfalar (4'ün katı hizalama için) + arka kapak pikepdf ile tek PDF'de birleştirilir.
7. **Temizlik** — `delete_source_pdf` değeri `true` ise, başarılı işlemden sonra orijinal öğrenci PDF'i silinir.

### Detection Region / Tespit Bölgesi

```
PDF Page (595 × 842 points, A4):

(0,0) ────────────────────────── (595,0)    ← Top / Üst
  │                                   │
  │       [not scanned / taranmaz]    │
  │                                   │
  │                                   │
(0,589) ────────────── (297,589)      │     ← 70% down / %70 aşağı
  │                    │              │
  │  DETECTION REGION  │              │
  │  TESPİT BÖLGESİ   │              │
  │  (bottom-left /    │              │
  │   sol alt)         │              │
  │                    │              │
(0,842) ────────────── (297,842) ── (595,842) ← Bottom / Alt
```

---

## Testing / Test

### EN: Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Run a specific test class
python -m pytest tests/test_engine.py::TestDetector -v
```

### TR: Testleri Çalıştırma

```bash
# Sanal ortamı etkinleştirin
source venv/bin/activate

# Tüm testleri çalıştırın
python -m pytest tests/ -v

# Kapsam raporu ile çalıştırın
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Belirli bir test sınıfını çalıştırın
python -m pytest tests/test_engine.py::TestDetector -v
```

### Generating Test Data / Test Verisi Oluşturma

```bash
# Generate 5 sample student PDFs + templates
# 5 örnek öğrenci PDF'i + şablonlar oluşturun
python -m tests.generate_test_data --count 5
```

**EN:** This creates sample student PDFs with Turkish names, a front template with `{{STUDENT_NAME}}` marker, and a back cover in `input_pdfs/`.

**TR:** Bu komut `input_pdfs/` içine Türkçe isimli örnek öğrenci PDF'leri, `{{STUDENT_NAME}}` işaretçili ön kapak şablonu ve arka kapak oluşturur.

---

## Troubleshooting / Sorun Giderme

### EN

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'src'` | Run from the project root directory, not from inside `src/` |
| `No valid student PDFs found` | Ensure student PDFs are in `input_pdfs/` and have text in the bottom-left region |
| Student name not detected | Check that the name is in the bottom-left region. Try adjusting `region_*_ratio` values in config |
| Turkish characters display incorrectly | Install DejaVu Sans: `sudo apt install fonts-dejavu-core` or place `DejaVuSans.ttf` in `fonts/` |
| `Front template not found` | Ensure `front_template.pdf` exists in `input_pdfs/` |
| `{{STUDENT_NAME}}` not replaced | The marker must be in the template's text layer (not a rasterized image) |
| Source PDFs not being deleted | Check `processing.delete_source_pdf` is `true` in config.json |
| Names have unwanted prefix | Set `detection.name_prefix` to the prefix text (e.g. `"Prepared for:"`) |

### TR

| Sorun | Çözüm |
|-------|-------|
| `ModuleNotFoundError: No module named 'src'` | Komutu proje kök dizininden çalıştırın, `src/` klasörünün içinden değil |
| `No valid student PDFs found` | Öğrenci PDF'lerinin `input_pdfs/` içinde olduğundan ve sol alt bölgede metin içerdiğinden emin olun |
| Öğrenci adı tespit edilmiyor | Adın sol alt bölgede olduğunu kontrol edin. Config'deki `region_*_ratio` değerlerini ayarlamayı deneyin |
| Türkçe karakterler yanlış görünüyor | DejaVu Sans yükleyin: `sudo apt install fonts-dejavu-core` veya `DejaVuSans.ttf` dosyasını `fonts/` klasörüne koyun |
| `Front template not found` hatası | `front_template.pdf` dosyasının `input_pdfs/` klasöründe var olduğundan emin olun |
| `{{STUDENT_NAME}}` değiştirilmiyor | İşaretçi şablonun metin katmanında olmalıdır (rasterleştirilmiş görüntü değil) |
| Kaynak PDF'ler silinmiyor | config.json'da `processing.delete_source_pdf` değerinin `true` olduğunu kontrol edin |
| İsimlerde istenmeyen ön ek var | `detection.name_prefix` alanını ön ek metnine ayarlayın (ör: `"Hazırlayan:"`) |

---

## Logging & Reports / Loglama & Raporlar

**EN:** The engine generates three types of output:

| Output | Location | Content |
|--------|----------|---------|
| Console | Terminal | Progress bar, summary table, errors |
| Log file | `logs/booklet_engine_YYYYMMDD_HHMMSS.log` | Full debug detail |
| Report CSV | `logs/report_YYYYMMDD_HHMMSS.csv` | Per-student metrics |

**TR:** Motor üç tür çıktı üretir:

| Çıktı | Konum | İçerik |
|-------|-------|--------|
| Konsol | Terminal | İlerleme çubuğu, özet tablo, hatalar |
| Log dosyası | `logs/booklet_engine_YYYYMMDD_HHMMSS.log` | Tam hata ayıklama detayı |
| Rapor CSV | `logs/report_YYYYMMDD_HHMMSS.csv` | Öğrenci bazlı metrikler |

---

## Scaling / Ölçeklendirme

| Scale / Ölçek | Strategy / Strateji |
|-------|----------|
| ~500 PDFs | Single machine, 4 workers / Tek makine, 4 işçi |
| ~2000 PDFs | Single machine, CPU core count workers / Tek makine, çekirdek sayısı kadar işçi |
| ~5000 PDFs | Chunked processing with checkpointing / Parçalı işlem |
| 10000+ PDFs | Distributed: Redis queue + multiple machines / Dağıtık: Redis kuyruğu + çoklu makine |

### Performance Tips / Performans İpuçları

**EN:**
- Increase `max_workers` to match your CPU core count
- Use an SSD for faster I/O
- Each worker uses ~50-100 MB peak memory
- Expected speed: ~50ms per PDF

**TR:**
- `max_workers` değerini CPU çekirdek sayınıza eşitleyin
- Daha hızlı I/O için SSD kullanın
- Her işçi en fazla ~50-100 MB bellek kullanır
- Beklenen hız: PDF başına ~50ms

---

## Error Handling / Hata Yönetimi

```
Level 1: Per-student isolation / Öğrenci bazlı izolasyon
   └── Each student failure is caught, never crashes the batch
       Her öğrenci hatası yakalanır, toplu işlemi çökertmez

Level 2: Input validation / Girdi doğrulama
   └── PDF validated before processing, config checked by Pydantic
       PDF işlemden önce doğrulanır, config Pydantic ile kontrol edilir

Level 3: Resource safety / Kaynak güvenliği
   └── All PDF handles in try/finally blocks
       Tüm PDF tanıtıcıları try/finally bloklarında

Level 4: Reporting / Raporlama
   └── Errors in console, log file, and report CSV
       Hatalar konsolda, log dosyasında ve rapor CSV'sinde
   └── Exit code 2 if any errors / Hata varsa çıkış kodu 2
```

---

## License / Lisans

MIT License — See [pyproject.toml](pyproject.toml) for details.
