@echo off
echo Updating calibration maps...
echo.

echo [1/2] Generating GeoJSON map...
python generate_map.py

echo.
echo [2/2] Generating HTML map...
python generate_html_map.py

echo.
echo ✓ All maps updated successfully!
echo.
pause
