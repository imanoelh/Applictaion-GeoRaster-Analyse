@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
set "PROJECT=%PROJECT_ROOT%\backend\data\fine_tuning\buildings\maxar_v1\benchmark_13M_test\qgis\13M_locked_test_ground_truth.qgz"
set "QGIS_DEFAULT=C:\Program Files\QGIS 3.40.14\bin\qgis-ltr-bin.exe"
set "QGIS_EXE=%QGIS_DEFAULT%"
if defined GEORASTER_QGIS_EXE if exist "%GEORASTER_QGIS_EXE%" set "QGIS_EXE=%GEORASTER_QGIS_EXE%"
if not exist "%PROJECT%" (
  echo 13M QGIS project missing: "%PROJECT%"
  exit /b 2
)
if not exist "%QGIS_EXE%" (
  echo QGIS was not found: "%QGIS_EXE%"
  exit /b 3
)
start "GeoRaster 13M TEST Ground Truth" "%QGIS_EXE%" "%PROJECT%"
exit /b 0
