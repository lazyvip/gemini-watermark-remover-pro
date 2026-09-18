@echo off
chcp 65001 >nul
title Gemini 无痕去水印工具（图片与视频）

echo =======================================================
echo          Gemini 无痕去水印工具（支持图片与视频）
echo =======================================================
echo.

:: 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境，请先安装 Python 3.8+ 并勾选 "Add Python to PATH"。
    echo 官方下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查并自动安装必要依赖 (包含自动音视频处理工具)
echo [1/3] 检查并配置运行依赖 (OpenCV, NumPy, FFmpeg自动引擎)...
python -c "import cv2, numpy, imageio_ffmpeg" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在自动补全运行依赖与 FFmpeg 驱动，请稍候...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo [提示] 镜像加速安装失败，正在使用默认源重试...
        pip install -r requirements.txt
    )
)
echo 依赖与音画处理引擎就绪！
echo.

:: 支持拖拽视频或图片文件到此批处理上
set "INPUT_FILE=%~1"

if "%INPUT_FILE%"=="" (
    echo 请输入需要去水印的图片/视频路径（或者直接将文件拖入此窗口并回车）:
    set /p INPUT_FILE="文件: "
)

:: 去除输入两边的引号
set "INPUT_FILE=%INPUT_FILE:"=%"

if not exist "%INPUT_FILE%" (
    echo.
    echo [错误] 找不到指定的文件: "%INPUT_FILE%"
    pause
    exit /b 1
)

echo.
echo [2/3] 开始按文件类型自动去水印...
python remove_watermark.py "%INPUT_FILE%"

echo.
echo =======================================================
echo [3/3] 处理完成！成品保存在原文件同目录下（图片为 _clean.png，视频为 _clean.mp4）。
echo =======================================================
pause
