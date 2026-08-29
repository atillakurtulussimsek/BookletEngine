@echo off
REM ============================================================
REM  Booklet Engine - Tek tikla calistirma scripti (Windows)
REM ============================================================
setlocal

REM Scriptin bulundugu dizine gec (her yerden calisabilsin)
cd /d "%~dp0"

echo ========================================
echo   Booklet Engine v1.0.0
echo   %DATE% %TIME%
echo ========================================
echo.

REM Sanal ortam kontrolu ve aktivasyonu
if exist ".venv\Scripts\activate.bat" (
    echo Sanal ortam aktif ediliyor...
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo Sanal ortam aktif ediliyor...
    call "venv\Scripts\activate.bat"
) else (
    echo [UYARI] Sanal ortam bulunamadi, sistem Python'u kullaniliyor.
    echo         Sanal ortam olusturmak icin: py -3 -m venv .venv
    echo.
)

REM Python kontrolu
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    echo [HATA] Python bulunamadi! Lutfen Python 3.10+ kurun.
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Python: %%v
echo.

REM Calistir
%PY% -m src.cli run --config config.json
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
    echo [OK] Islem basariyla tamamlandi.
) else if %EXIT_CODE% EQU 2 (
    echo [UYARI] Islem tamamlandi fakat bazi hatalar olustu. Loglara bakin.
) else (
    echo [HATA] Islem basarisiz oldu ^(cikis kodu: %EXIT_CODE%^).
)

echo.
pause
exit /b %EXIT_CODE%
