================================================================================
PEAKLEDGER CORE ENGINE - WINDOWS COMPILATION & EXECUTION GUIDE
================================================================================

This guide provides instructions to compile and run the PeakLedger forensic
backend and analyst workstation on your Windows laptop (tested on Windows 10/11
with NVIDIA GeForce RTX 3050 / 4050 / 4060 / 4070 mobile GPUs).

--------------------------------------------------------------------------------
OPTION 1: RUNNING VIA WSL2 (RECOMMENDED - 100% NATIVE PERFORMANCE)
--------------------------------------------------------------------------------
WSL2 (Windows Subsystem for Linux 2) uses direct CUDA GPU pass-through from
your Windows NVIDIA driver (/usr/lib/wsl/lib). It requires zero emulation and
provides maximum GPU performance.

Step 1: Open PowerShell as Administrator and run:
  wsl --install -d Ubuntu-22.04

Step 2: Inside the Ubuntu-22.04 terminal, install packages:
  sudo apt-get update && sudo apt-get install -y \
      build-essential cmake git pkg-config \
      libavcodec-dev libavformat-dev libavutil-dev \
      libssl-dev libsqlite3-dev python3-pip python3-dev

Step 3: Install CUDA 12 for WSL-Ubuntu (if not already present):
  wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin
  sudo mv cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600
  sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/3bf863cc.pub
  sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/ /"
  sudo apt-get update && sudo apt-get -y install cuda-toolkit-12-4

Step 4: Navigate to the peakledger directory inside WSL:
  cd /mnt/c/path/to/peakledger
  make clean
  make -j$(nproc)

Step 5: Run the automated forensic test pipeline:
  ./fresh_run.sh evidence/sample_pristine.mp4 evidence/sample_suspect.mp4 "CASE_2026_01" "CCTV_Terminal_NorthGate"

Step 6: Run unit test suites:
  ./bin/test_crypto_merkle
  ./bin/test_forensic_attribute_engine
  ./bin/test_ledger_db

--------------------------------------------------------------------------------
OPTION 2: NATIVE WINDOWS COMPILATION (VISUAL STUDIO 2022 & CMAKE)
--------------------------------------------------------------------------------
Prerequisites:
  1. Visual Studio 2022 (Community or Professional) with "Desktop development with C++"
  2. NVIDIA CUDA Toolkit 12.x for Windows
  3. TensorRT 10.x / 11.x for Windows (extracted, e.g. C:\TensorRT)
  4. Microsoft vcpkg (for FFmpeg, OpenSSL, SQLite3)

Step 1: Install C++ dependencies via vcpkg:
  git clone https://github.com/microsoft/vcpkg.git C:\vcpkg
  cd C:\vcpkg
  .\bootstrap-vcpkg.bat
  .\vcpkg.exe install ffmpeg:x64-windows openssl:x64-windows sqlite3:x64-windows

Step 2: Compile with CMake:
  cd \path\to\peakledger
  cmake -B build -G "Visual Studio 17 2022" -A x64 ^
      -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake ^
      -DCUDA_TOOLKIT_ROOT_DIR="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4" ^
      -DTensorRT_DIR="C:\TensorRT"
  cmake --build build --config Release --parallel

Step 3: Run the compiled backend:
  .\build\bin\Release\forensic_backend.exe --verify evidence\sample_suspect.mp4 --id "CASE_2026_01" --db evidence\ledger.db

--------------------------------------------------------------------------------
OPTION 3: RUNNING THE PYTHON FORENSIC WORKSTATION UI ON WINDOWS
--------------------------------------------------------------------------------
You can run the interactive analyst workstation UI natively on Windows!

Step 1: Open Command Prompt or PowerShell, navigate to peakledger:
  cd \path\to\peakledger

Step 2: Install Python dependencies:
  pip install PyQt6 pillow opencv-python numpy matplotlib python-docx

Step 3: Launch the UI:
  python ui\main.py
  (Or simply double-click run_ui_windows.bat)

--------------------------------------------------------------------------------
MEMORY PROFILE TUNING FOR LAPTOPS:
--------------------------------------------------------------------------------
PeakLedger is specifically built with a `VramProfile::LAPTOP` profile.
Total peak VRAM footprint is kept under 2.5 GB, ensuring smooth, crash-free
execution on 4GB-6GB mobile GPUs (such as RTX 3050 Laptop GPUs).
================================================================================
