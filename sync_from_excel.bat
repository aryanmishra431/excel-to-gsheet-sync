@echo off
cd /d "%~dp0"
python sync_to_sheet.py --source excel --source-path "C:\Users\kanth\OneDrive\Documents\ExcelData" --dest-id 1zburt8zMlb0YQrcvdSyCJi2EPlo9e41JiUyB4RX4A4E --dest-tab Sheet1
echo.
pause
