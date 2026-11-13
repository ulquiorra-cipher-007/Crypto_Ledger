@echo off
REM PeakLedger Windows Build Script
REM Requires Visual Studio 2022, CMake, CUDA 12, and vcpkg

echo ======================================================================
echo Building PeakLedger Core Backend on Windows
echo ======================================================================

set VCPKG_ROOT=C:\vcpkg
set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
set TENSORRT_PATH=C:\TensorRT

if not exist "%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake" (
    echo [WARNING] vcpkg.cmake not found at %VCPKG_ROOT%.
    echo Please ensure vcpkg is installed and set VCPKG_ROOT in this script.
)

cmake -B build -G "Visual Studio 17 2022" -A x64 ^
    -DCMAKE_TOOLCHAIN_FILE="%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake" ^
    -DCUDA_TOOLKIT_ROOT_DIR="%CUDA_PATH%" ^
    -DTensorRT_DIR="%TENSORRT_PATH%"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed.
    exit /b %ERRORLEVEL%
)

cmake --build build --config Release --parallel

if %ERRORLEVEL% EQU 0 (
    echo ======================================================================
    echo Build Succeeded! Binaries located in build\bin\Release\
    echo ======================================================================
) else (
    echo [ERROR] Build failed.
)
