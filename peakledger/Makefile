CXX ?= g++
CUDA_DIR ?= $(shell if [ -d /usr/local/cuda ]; then echo /usr/local/cuda; elif [ -d /usr/local/cuda-13 ]; then echo /usr/local/cuda-13; elif [ -d /usr/local/cuda-12 ]; then echo /usr/local/cuda-12; else echo /usr/local/cuda; fi)
NVCC ?= $(shell if [ -x $(CUDA_DIR)/bin/nvcc ]; then echo $(CUDA_DIR)/bin/nvcc; else which nvcc; fi)

PKG_CFLAGS = $(shell pkg-config --cflags libavcodec libavformat libavutil sqlite3 libcrypto 2>/dev/null)
PKG_LIBS = $(shell pkg-config --libs libavcodec libavformat libavutil sqlite3 libcrypto 2>/dev/null)

CXXFLAGS = -std=c++20 -O3 -Wall -Wextra -I./include -I$(CUDA_DIR)/include -I/usr/include/x86_64-linux-gnu -fPIC $(PKG_CFLAGS)
NVCCFLAGS = -std=c++17 -O3 -I./include -I$(CUDA_DIR)/include \
            -gencode arch=compute_86,code=sm_86 \
            -gencode arch=compute_89,code=sm_89 \
            -gencode arch=compute_120,code=sm_120 \
            -gencode arch=compute_89,code=compute_89 \
            -Xcompiler -fPIC

LDFLAGS = -L$(CUDA_DIR)/lib64 -L/usr/lib/x86_64-linux-gnu \
          -lavcodec -lavformat -lavutil -lsqlite3 -lcrypto -lnvinfer -lrt -lpthread -lcudart \
          -Wl,-rpath,'$$ORIGIN/../lib' -Wl,-rpath,'$(CUDA_DIR)/lib64' -Wl,--disable-new-dtags

SRC_DIR = src
BUILD_DIR = build
BIN_DIR = bin
APPDIR_BIN = AppDir/usr/bin

TARGET = $(BIN_DIR)/forensic_backend
APPDIR_TARGET = $(APPDIR_BIN)/forensic_backend

OBJS = $(BUILD_DIR)/cuda_spatial_hash.o \
       $(BUILD_DIR)/cuda_preprocess.o \
       $(BUILD_DIR)/crypto_merkle.o \
       $(BUILD_DIR)/ledger_db.o \
       $(BUILD_DIR)/nvdec_decoder.o \
       $(BUILD_DIR)/tamper_extractor.o \
       $(BUILD_DIR)/tensorrt_infer.o \
       $(BUILD_DIR)/trt_inference.o \
       $(BUILD_DIR)/motion_tracker.o \
       $(BUILD_DIR)/forensic_attribute_engine.o \
       $(BUILD_DIR)/main.o

TESTS = $(BIN_DIR)/test_cuda_preprocess \
        $(BIN_DIR)/test_trt_inference \
        $(BIN_DIR)/test_motion_tracker \
        $(BIN_DIR)/test_crypto_merkle \
        $(BIN_DIR)/test_cuda_hash \
        $(BIN_DIR)/test_ledger_db \
        $(BIN_DIR)/test_forensic_attribute_engine \
        $(BIN_DIR)/test_ring_buffer

all: directories $(TARGET) $(APPDIR_TARGET) $(TESTS)

directories:
	@mkdir -p $(BUILD_DIR) $(BIN_DIR) $(APPDIR_BIN) AppDir/usr/lib AppDir/ui evidence models

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(APPDIR_TARGET): $(TARGET)
	cp $(TARGET) $(APPDIR_TARGET)
	cp -r ui/* AppDir/ui/ 2>/dev/null || true
	cp -r models AppDir/ 2>/dev/null || true

$(BUILD_DIR)/cuda_spatial_hash.o: $(SRC_DIR)/cuda_spatial_hash.cu include/cuda_spatial_hash.cuh include/common.hpp
	$(NVCC) $(NVCCFLAGS) -c $< -o $@

$(BUILD_DIR)/cuda_preprocess.o: $(SRC_DIR)/cuda_preprocess.cu include/cuda_preprocess.cuh
	$(NVCC) $(NVCCFLAGS) -c $< -o $@

$(BUILD_DIR)/crypto_merkle.o: $(SRC_DIR)/crypto_merkle.cpp include/crypto_merkle.hpp include/common.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/ledger_db.o: $(SRC_DIR)/ledger_db.cpp include/ledger_db.hpp include/common.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/nvdec_decoder.o: $(SRC_DIR)/nvdec_decoder.cpp include/nvdec_decoder.hpp include/common.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/tamper_extractor.o: $(SRC_DIR)/tamper_extractor.cpp include/tamper_extractor.hpp include/common.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/tensorrt_infer.o: $(SRC_DIR)/tensorrt_infer.cpp include/tensorrt_infer.hpp include/common.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/trt_inference.o: $(SRC_DIR)/trt_inference.cpp include/trt_inference.hpp include/cuda_preprocess.cuh
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/motion_tracker.o: $(SRC_DIR)/motion_tracker.cpp include/motion_tracker.hpp include/ring_buffer.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/forensic_attribute_engine.o: $(SRC_DIR)/forensic_attribute_engine.cpp include/forensic_attribute_engine.hpp include/common.hpp include/motion_tracker.hpp include/nvdec_decoder.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/main.o: $(SRC_DIR)/main.cpp include/common.hpp include/ring_buffer.hpp include/cuda_preprocess.cuh include/trt_inference.hpp include/motion_tracker.hpp include/forensic_attribute_engine.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Test binaries
$(BIN_DIR)/test_cuda_preprocess: tests/test_cuda_preprocess.cu $(BUILD_DIR)/cuda_preprocess.o
	$(NVCC) $(NVCCFLAGS) $^ -o $@ -L$(CUDA_DIR)/lib64 -lcudart

$(BIN_DIR)/test_trt_inference: tests/test_trt_inference.cpp $(BUILD_DIR)/trt_inference.o $(BUILD_DIR)/cuda_preprocess.o
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

$(BIN_DIR)/test_motion_tracker: tests/test_motion_tracker.cpp $(BUILD_DIR)/motion_tracker.o
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

$(BIN_DIR)/test_crypto_merkle: tests/test_crypto_merkle.cpp $(BUILD_DIR)/crypto_merkle.o
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

$(BIN_DIR)/test_cuda_hash: tests/test_cuda_hash.cu $(BUILD_DIR)/cuda_spatial_hash.o
	$(NVCC) $(NVCCFLAGS) $^ -o $@ -L$(CUDA_DIR)/lib64 -lcudart

$(BIN_DIR)/test_ledger_db: tests/test_ledger_db.cpp $(BUILD_DIR)/ledger_db.o $(BUILD_DIR)/crypto_merkle.o
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

$(BIN_DIR)/test_forensic_attribute_engine: tests/test_forensic_attribute_engine.cpp $(BUILD_DIR)/forensic_attribute_engine.o $(BUILD_DIR)/ledger_db.o $(BUILD_DIR)/crypto_merkle.o
	$(CXX) $(CXXFLAGS) $^ -o $@ $(LDFLAGS)

$(BIN_DIR)/test_ring_buffer: tests/test_ring_buffer.cpp
	$(CXX) $(CXXFLAGS) $^ -o $@ -lrt -lpthread

bundle: all
	bash scripts/bundle_appdir.sh

clean:
	rm -rf $(BUILD_DIR)/*.o $(TARGET) $(APPDIR_TARGET) $(TESTS)

.PHONY: all directories bundle clean
