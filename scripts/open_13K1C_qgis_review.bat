@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "PROJECT=%PROJECT_ROOT%\backend\data\fine_tuning\buildings\maxar_v1\qgis\13K1C_assisted_review.qgz"
set "QGIS_DEFAULT=C:\Program Files\QGIS 3.40.14\bin\qgis-ltr-bin.exe"
set "QGIS_PYTHON=C:\Program Files\QGIS 3.40.14\bin\python-qgis-ltr.bat"
set "QGIS_EXE=%QGIS_DEFAULT%"

if defined GEORASTER_QGIS_EXE if exist "%GEORASTER_QGIS_EXE%" set "QGIS_EXE=%GEORASTER_QGIS_EXE%"
if not exist "%QGIS_EXE%" (
  if defined GEORASTER_QGIS_EXE echo Configured GEORASTER_QGIS_EXE was not found: "%GEORASTER_QGIS_EXE%"
  if not exist "%QGIS_DEFAULT%" echo QGIS 3.40.14 was not found: "%QGIS_DEFAULT%"
  exit /b 2
)
if not exist "%PROJECT%" (
  if not exist "%QGIS_PYTHON%" (
    echo QGIS Python launcher was not found: "%QGIS_PYTHON%"
    exit /b 3
  )
  call "%QGIS_PYTHON%" "%PROJECT_ROOT%\scripts\build_13K1C_qgis_project.py"
  if errorlevel 1 exit /b 1
  if not exist "%PROJECT%" (
    echo Project generation did not create: "%PROJECT%"
    exit /b 4
  )
)

start "GeoRaster 13K.1C QGIS Review" "%QGIS_EXE%" "%PROJECT%"
exit /b 0
