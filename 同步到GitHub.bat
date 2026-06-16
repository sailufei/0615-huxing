@echo off
cd /d "d:\guojiabao008\Desktop\Cursor workspace\户型盘点工具"
echo ========================================
echo   户型盘点工具 - 一键同步到 GitHub
echo ========================================
echo.
set /p MSG="请输入改动说明（直接回车默认"更新"）:
if "%MSG%"=="" set MSG=更新
echo.
echo 正在同步...
git add -A
git commit -m "%MSG%"
git push
echo.
echo ========================================
echo   同步完成！按任意键关闭
echo ========================================
pause >nul
