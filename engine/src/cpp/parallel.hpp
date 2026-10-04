#pragma once

#include <atomic>
#include <cstddef>
#include <exception>
#include <mutex>
#include <thread>
#include <vector>

namespace quantly {

// threads < 0 means "auto" (hardware concurrency); 0 and 1 run inline.
inline int resolve_threads(int requested, std::size_t tasks) {
    unsigned hw = std::thread::hardware_concurrency();
    std::size_t n = requested < 0 ? (hw ? hw : 1) : static_cast<std::size_t>(requested);
    if (n < 1) {
        n = 1;
    }
    if (n > tasks) {
        n = tasks;
    }
    return static_cast<int>(n == 0 ? 1 : n);
}

// run fn(task) for task in [0, n_tasks). workers pull task indices from a shared
// atomic counter, so the schedule varies with thread count but each task is
// self-contained and writes only its own slice: results never depend on it.
template <class F>
void parallel_for(std::size_t n_tasks, int threads, F&& fn) {
    int n = resolve_threads(threads, n_tasks);
    if (n <= 1) {
        for (std::size_t t = 0; t < n_tasks; ++t) {
            fn(t);
        }
        return;
    }

    std::atomic<std::size_t> next{0};
    std::exception_ptr error;
    std::mutex error_mutex;
    auto worker = [&]() {
        try {
            for (std::size_t t = next.fetch_add(1); t < n_tasks; t = next.fetch_add(1)) {
                fn(t);
            }
        } catch (...) {
            std::lock_guard<std::mutex> lock(error_mutex);
            if (!error) {
                error = std::current_exception();
            }
            next.store(n_tasks);
        }
    };

    std::vector<std::thread> pool;
    pool.reserve(static_cast<std::size_t>(n - 1));
    for (int i = 1; i < n; ++i) {
        pool.emplace_back(worker);
    }
    worker();  // the caller works too
    for (auto& th : pool) {
        th.join();
    }
    if (error) {
        std::rethrow_exception(error);
    }
}

}  // namespace quantly
