#pragma once

#include "common.hpp"
#include <atomic>
#include <cstring>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdexcept>
#include <iostream>
#include <new>

namespace Forensic {

// 64-byte cache line aligned Telemetry frame (640 bytes total)
struct alignas(64) TelemetryFrame {
    int64_t pts{0};
    uint64_t frame_index{0};
    uint8_t live_hash[SHA256_DIGEST_LENGTH]{0};
    uint8_t baseline_hash[SHA256_DIGEST_LENGTH]{0};
    uint8_t is_match{1};
    uint8_t has_baseline{1};
    uint16_t reserved{0};
    uint32_t residual_energy{0};
    uint64_t timestamp_ns{0};
    uint8_t grid_signature[GRID_CELLS]{0}; // 512 bytes luminance grid
    uint8_t _pad[32]{0};                  // Explicit padding to align to 640 bytes
};

static_assert(sizeof(TelemetryFrame) == 640, "TelemetryFrame must be exactly 640 bytes");
static_assert(alignof(TelemetryFrame) == 64, "TelemetryFrame must be 64-byte aligned");

// Lock-Free POSIX Shared Memory Block with separate cache lines to prevent false sharing
struct alignas(64) ForensicSharedMemory {
    uint32_t magic;                     // 0x4653484D ("FSHM")
    uint32_t version;                   // 1
    uint32_t capacity;                  // 256
    uint32_t _padding0;
    uint8_t  _pad1[48];                 // Align write_seq to offset 64

    alignas(64) std::atomic<uint64_t> write_seq; // Producer sequence (release order)
    uint8_t  _pad2[56];                 // Align read_seq to offset 128

    alignas(64) std::atomic<uint64_t> read_seq;  // Consumer sequence (acquire order)
    uint8_t  _pad3[56];                 // Align is_tampered to offset 192

    alignas(64) std::atomic<uint32_t> is_tampered;
    uint32_t _pad4;
    std::atomic<int64_t> tamper_pts;
    char tamper_image_path[512];
    std::atomic<uint32_t> is_completed;
    uint32_t _pad5;
    std::atomic<uint64_t> total_frames_processed;
    std::atomic<uint64_t> total_frames_matched;
    std::atomic<uint64_t> total_frames_tampered;
    uint8_t  _pad6[16];                 // Align slots to offset 768

    alignas(64) TelemetryFrame slots[RING_BUFFER_CAPACITY];
};

static_assert(sizeof(ForensicSharedMemory) == 164608, "ForensicSharedMemory size must be exactly 164608 bytes");
static_assert(offsetof(ForensicSharedMemory, write_seq) == 64, "write_seq must be at offset 64");
static_assert(offsetof(ForensicSharedMemory, read_seq) == 128, "read_seq must be at offset 128");
static_assert(offsetof(ForensicSharedMemory, is_tampered) == 192, "is_tampered must be at offset 192");
static_assert(offsetof(ForensicSharedMemory, slots) == 768, "slots must be at offset 768");

class ShmProducer {
public:
    explicit ShmProducer(const std::string& name = DEFAULT_SHM_NAME, bool create = true) 
        : name_(name), shm_fd_(-1), shm_ptr_(nullptr), size_(sizeof(ForensicSharedMemory)) {
        
        if (create) {
            shm_unlink(name_.c_str());
        }

        int flags = O_RDWR;
        if (create) {
            flags |= O_CREAT | O_TRUNC;
        }

        shm_fd_ = shm_open(name_.c_str(), flags, 0666);
        if (shm_fd_ < 0) {
            throw std::runtime_error("shm_open producer failed: " + std::string(strerror(errno)));
        }

        if (create) {
            if (ftruncate(shm_fd_, size_) != 0) {
                close(shm_fd_);
                throw std::runtime_error("ftruncate failed: " + std::string(strerror(errno)));
            }
        }

        void* ptr = mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0);
        if (ptr == MAP_FAILED) {
            close(shm_fd_);
            throw std::runtime_error("mmap producer failed: " + std::string(strerror(errno)));
        }

        if (create) {
            shm_ptr_ = new (ptr) ForensicSharedMemory();
            shm_ptr_->magic = 0x4653484D; // "FSHM"
            shm_ptr_->version = 1;
            shm_ptr_->capacity = RING_BUFFER_CAPACITY;
            shm_ptr_->_padding0 = 0;
            shm_ptr_->write_seq.store(0, std::memory_order_relaxed);
            shm_ptr_->read_seq.store(0, std::memory_order_relaxed);
            shm_ptr_->is_tampered.store(0, std::memory_order_relaxed);
            shm_ptr_->tamper_pts.store(-1, std::memory_order_relaxed);
            shm_ptr_->tamper_image_path[0] = '\0';
            shm_ptr_->is_completed.store(0, std::memory_order_relaxed);
            shm_ptr_->total_frames_processed.store(0, std::memory_order_relaxed);
            shm_ptr_->total_frames_matched.store(0, std::memory_order_relaxed);
            shm_ptr_->total_frames_tampered.store(0, std::memory_order_relaxed);
            for (size_t i = 0; i < RING_BUFFER_CAPACITY; ++i) {
                shm_ptr_->slots[i] = TelemetryFrame{};
            }
        } else {
            shm_ptr_ = static_cast<ForensicSharedMemory*>(ptr);
        }
    }

    ~ShmProducer() {
        if (shm_ptr_ && shm_ptr_ != MAP_FAILED) {
            munmap(shm_ptr_, size_);
        }
        if (shm_fd_ >= 0) {
            close(shm_fd_);
        }
    }

    void push_telemetry(const TelemetryFrame& frame) {
        uint64_t current_write = shm_ptr_->write_seq.load(std::memory_order_relaxed);
        size_t slot_idx = current_write % RING_BUFFER_CAPACITY;
        
        // Write payload to ring slot
        shm_ptr_->slots[slot_idx] = frame;

        // Release order: ensures payload is visible to consumers reading with acquire
        shm_ptr_->write_seq.store(current_write + 1, std::memory_order_release);
        shm_ptr_->total_frames_processed.fetch_add(1, std::memory_order_relaxed);
        if (frame.is_match) {
            shm_ptr_->total_frames_matched.fetch_add(1, std::memory_order_relaxed);
        } else {
            shm_ptr_->total_frames_tampered.fetch_add(1, std::memory_order_relaxed);
        }
    }

    void set_tamper_flag(int64_t pts, const std::string& image_path) {
        shm_ptr_->tamper_pts.store(pts, std::memory_order_relaxed);
        std::strncpy(shm_ptr_->tamper_image_path, image_path.c_str(), sizeof(shm_ptr_->tamper_image_path) - 1);
        shm_ptr_->tamper_image_path[sizeof(shm_ptr_->tamper_image_path) - 1] = '\0';
        shm_ptr_->is_tampered.store(1, std::memory_order_release);
    }

    void set_completed() {
        shm_ptr_->is_completed.store(1, std::memory_order_release);
    }

    ForensicSharedMemory* raw() { return shm_ptr_; }

private:
    std::string name_;
    int shm_fd_{-1};
    ForensicSharedMemory* shm_ptr_{nullptr};
    size_t size_;
};

class ShmConsumer {
public:
    explicit ShmConsumer(const std::string& name = DEFAULT_SHM_NAME)
        : name_(name), shm_fd_(-1), shm_ptr_(nullptr), size_(sizeof(ForensicSharedMemory)) {
        
        shm_fd_ = shm_open(name_.c_str(), O_RDWR, 0666);
        if (shm_fd_ < 0) {
            throw std::runtime_error("shm_open consumer failed: " + std::string(strerror(errno)));
        }

        void* ptr = mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd_, 0);
        if (ptr == MAP_FAILED) {
            close(shm_fd_);
            throw std::runtime_error("mmap consumer failed: " + std::string(strerror(errno)));
        }

        shm_ptr_ = static_cast<ForensicSharedMemory*>(ptr);
        if (shm_ptr_->magic != 0x4653484D) {
            munmap(shm_ptr_, size_);
            close(shm_fd_);
            throw std::runtime_error("Invalid shared memory magic header");
        }
    }

    ~ShmConsumer() {
        if (shm_ptr_ && shm_ptr_ != MAP_FAILED) {
            munmap(shm_ptr_, size_);
        }
        if (shm_fd_ >= 0) {
            close(shm_fd_);
        }
    }

    bool poll_latest(TelemetryFrame& out_frame, uint64_t& inout_last_seq) {
        uint64_t head = shm_ptr_->write_seq.load(std::memory_order_acquire);
        if (head <= inout_last_seq) {
            return false; // No new frames
        }
        
        // If producer lapped the consumer beyond capacity, fast-forward to oldest valid
        if (head > inout_last_seq + RING_BUFFER_CAPACITY) {
            inout_last_seq = head - RING_BUFFER_CAPACITY;
        }

        size_t slot_idx = inout_last_seq % RING_BUFFER_CAPACITY;
        out_frame = shm_ptr_->slots[slot_idx];
        inout_last_seq++;
        shm_ptr_->read_seq.store(inout_last_seq, std::memory_order_release);
        return true;
    }

    bool is_tampered(int64_t& out_pts, std::string& out_path) const {
        if (shm_ptr_->is_tampered.load(std::memory_order_acquire)) {
            out_pts = shm_ptr_->tamper_pts.load(std::memory_order_relaxed);
            out_path = shm_ptr_->tamper_image_path;
            return true;
        }
        return false;
    }

    bool is_completed() const {
        return shm_ptr_->is_completed.load(std::memory_order_acquire) != 0;
    }

    const ForensicSharedMemory* raw() const { return shm_ptr_; }

private:
    std::string name_;
    int shm_fd_{-1};
    ForensicSharedMemory* shm_ptr_{nullptr};
    size_t size_;
};

} // namespace Forensic
