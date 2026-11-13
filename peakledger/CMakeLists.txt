cmake_minimum_required(VERSION 3.20)
project(PeakLedger LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# CUDA Architectures (supports Ampere sm_86, Ada Lovelace sm_89, Blackwell sm_120)
if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
    set(CMAKE_CUDA_ARCHITECTURES "86;89")
endif()

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES}
)

# Find Packages
find_package(CUDAToolkit REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

# SQLite3
find_package(SQLite3 REQUIRED)

# FFmpeg (avcodec, avformat, avutil)
find_path(AVCODEC_INCLUDE_DIR libavcodec/avcodec.h)
find_library(AVCODEC_LIBRARY avcodec)
find_library(AVFORMAT_LIBRARY avformat)
find_library(AVUTIL_LIBRARY avutil)

# TensorRT
find_path(TENSORRT_INCLUDE_DIR NvInfer.h
    HINTS 
    $ENV{TENSORRT_DIR}/include 
    /usr/include/x86_64-linux-gnu 
    "C:/TensorRT/include"
)
find_library(TENSORRT_LIBRARY nvinfer
    HINTS 
    $ENV{TENSORRT_DIR}/lib 
    /usr/lib/x86_64-linux-gnu 
    "C:/TensorRT/lib"
)

if(AVCODEC_INCLUDE_DIR)
    include_directories(${AVCODEC_INCLUDE_DIR})
endif()
if(TENSORRT_INCLUDE_DIR)
    include_directories(${TENSORRT_INCLUDE_DIR})
endif()

# Core Backend Source Files
set(BACKEND_SOURCES
    src/crypto_merkle.cpp
    src/cuda_preprocess.cu
    src/cuda_spatial_hash.cu
    src/forensic_attribute_engine.cpp
    src/ledger_db.cpp
    src/motion_tracker.cpp
    src/nvdec_decoder.cpp
    src/tamper_extractor.cpp
    src/tensorrt_infer.cpp
    src/trt_inference.cpp
)

# Common Libraries to Link
set(CORE_LIBS
    CUDA::cudart
    OpenSSL::Crypto
    SQLite::SQLite3
    ${AVCODEC_LIBRARY}
    ${AVFORMAT_LIBRARY}
    ${AVUTIL_LIBRARY}
    ${TENSORRT_LIBRARY}
    Threads::Threads
)

if(UNIX)
    list(APPEND CORE_LIBS rt dl)
endif()

# Main Backend Binary
add_executable(forensic_backend
    src/main.cpp
    ${BACKEND_SOURCES}
)
target_link_libraries(forensic_backend PRIVATE ${CORE_LIBS})

# Unit Test Executables
add_executable(test_crypto_merkle tests/test_crypto_merkle.cpp src/crypto_merkle.cpp)
target_link_libraries(test_crypto_merkle PRIVATE OpenSSL::Crypto Threads::Threads)

add_executable(test_cuda_preprocess tests/test_cuda_preprocess.cu src/cuda_preprocess.cu)
target_link_libraries(test_cuda_preprocess PRIVATE CUDA::cudart)

add_executable(test_cuda_hash tests/test_cuda_hash.cu src/cuda_spatial_hash.cu)
target_link_libraries(test_cuda_hash PRIVATE CUDA::cudart)

add_executable(test_ledger_db tests/test_ledger_db.cpp src/ledger_db.cpp src/crypto_merkle.cpp)
target_link_libraries(test_ledger_db PRIVATE SQLite::SQLite3 OpenSSL::Crypto Threads::Threads)

add_executable(test_motion_tracker tests/test_motion_tracker.cpp src/motion_tracker.cpp)
target_link_libraries(test_motion_tracker PRIVATE ${CORE_LIBS})

add_executable(test_trt_inference tests/test_trt_inference.cpp src/trt_inference.cpp src/cuda_preprocess.cu)
target_link_libraries(test_trt_inference PRIVATE ${CORE_LIBS})

add_executable(test_forensic_attribute_engine tests/test_forensic_attribute_engine.cpp src/forensic_attribute_engine.cpp src/ledger_db.cpp src/crypto_merkle.cpp)
target_link_libraries(test_forensic_attribute_engine PRIVATE ${CORE_LIBS})

# Set output directories
set_target_properties(forensic_backend PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_crypto_merkle PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_cuda_preprocess PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_cuda_hash PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_ledger_db PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_motion_tracker PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_trt_inference PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
set_target_properties(test_forensic_attribute_engine PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/bin")
