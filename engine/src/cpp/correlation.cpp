#include "correlation.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <utility>
#include <vector>

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#endif

#include "parallel.hpp"

namespace quantly {

namespace {

std::vector<double> row_means(const double* data, std::size_t rows, std::size_t cols) {
    std::vector<double> means(rows, 0.0);
    for (std::size_t i = 0; i < rows; ++i) {
        const double* row = data + i * cols;
        double sum = 0.0;
        for (std::size_t k = 0; k < cols; ++k) {
            sum += row[k];
        }
        means[i] = cols ? sum / static_cast<double>(cols) : 0.0;
    }
    return means;
}

}  // namespace

void covariance_matrix(const double* data, std::size_t rows, std::size_t cols, int ddof,
                       double* out) {
    std::vector<double> means = row_means(data, rows, cols);
    double denom = static_cast<double>(cols) - static_cast<double>(ddof);
    for (std::size_t i = 0; i < rows; ++i) {
        for (std::size_t j = i; j < rows; ++j) {
            const double* ri = data + i * cols;
            const double* rj = data + j * cols;
            double acc = 0.0;
            for (std::size_t k = 0; k < cols; ++k) {
                acc += (ri[k] - means[i]) * (rj[k] - means[j]);
            }
            double cov = denom > 0.0 ? acc / denom : 0.0;
            out[i * rows + j] = cov;
            out[j * rows + i] = cov;
        }
    }
}

namespace {

constexpr std::size_t kTile = 16;   // output tile edge
constexpr std::size_t kPanel = 256; // observations per packed panel

// acc (kTile x kTile) += A^T B over one packed panel. a and b are laid out
// k-major (a[k * kTile + i]), so the inner j loop is contiguous and vectorizes
// without reassociating any sum. a 4x8 register block keeps accumulators out of
// memory.
#if defined(__GNUC__) || defined(__clang__)
#define QUANTLY_INLINE inline __attribute__((always_inline))
#else
#define QUANTLY_INLINE inline
#endif

QUANTLY_INLINE void panel_kernel_body(const double* a, const double* b, std::size_t kb,
                                      double* acc) {
    for (std::size_t mi = 0; mi < kTile; mi += 4) {
        for (std::size_t nj = 0; nj < kTile; nj += 8) {
            double c[4][8] = {};
            for (std::size_t k = 0; k < kb; ++k) {
                const double* ak = a + k * kTile + mi;
                const double* bk = b + k * kTile + nj;
                for (int i = 0; i < 4; ++i) {
                    for (int j = 0; j < 8; ++j) {
                        c[i][j] += ak[i] * bk[j];
                    }
                }
            }
            for (std::size_t i = 0; i < 4; ++i) {
                for (std::size_t j = 0; j < 8; ++j) {
                    acc[(mi + i) * kTile + nj + j] += c[i][j];
                }
            }
        }
    }
}

void panel_kernel_generic(const double* a, const double* b, std::size_t kb, double* acc) {
    panel_kernel_body(a, b, kb, acc);
}

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
// the same 4x8 register block in explicit avx2+fma intrinsics, chosen at runtime
// so one wheel runs on any x86-64 cpu. the baseline build only assumes sse2.
__attribute__((target("avx2,fma"))) void panel_kernel_avx2(const double* a, const double* b,
                                                           std::size_t kb, double* acc) {
    for (std::size_t mi = 0; mi < kTile; mi += 4) {
        for (std::size_t nj = 0; nj < kTile; nj += 8) {
            __m256d c[4][2];
            for (int i = 0; i < 4; ++i) {
                c[i][0] = _mm256_setzero_pd();
                c[i][1] = _mm256_setzero_pd();
            }
            for (std::size_t k = 0; k < kb; ++k) {
                const double* ak = a + k * kTile + mi;
                const double* bk = b + k * kTile + nj;
                __m256d b0 = _mm256_loadu_pd(bk);
                __m256d b1 = _mm256_loadu_pd(bk + 4);
                for (int i = 0; i < 4; ++i) {
                    __m256d av = _mm256_broadcast_sd(ak + i);
                    c[i][0] = _mm256_fmadd_pd(av, b0, c[i][0]);
                    c[i][1] = _mm256_fmadd_pd(av, b1, c[i][1]);
                }
            }
            for (std::size_t i = 0; i < 4; ++i) {
                double* row = acc + (mi + i) * kTile + nj;
                _mm256_storeu_pd(row, _mm256_add_pd(_mm256_loadu_pd(row), c[i][0]));
                _mm256_storeu_pd(row + 4, _mm256_add_pd(_mm256_loadu_pd(row + 4), c[i][1]));
            }
        }
    }
}
#define QUANTLY_HAVE_AVX2_DISPATCH 1
#endif

using PanelKernel = void (*)(const double*, const double*, std::size_t, double*);

PanelKernel select_kernel() {
#ifdef QUANTLY_HAVE_AVX2_DISPATCH
    // QUANTLY_DISABLE_AVX2 forces the portable path (tests, benchmarking)
    if (!std::getenv("QUANTLY_DISABLE_AVX2") && __builtin_cpu_supports("avx2") &&
        __builtin_cpu_supports("fma")) {
        return &panel_kernel_avx2;
    }
#endif
    return &panel_kernel_generic;
}

// copy rows [r0, r0 + kTile) of z, observations [k0, k0 + kb), into k-major
// layout, zero padding rows past the end
void pack(const double* z, std::size_t rows, std::size_t cols, std::size_t r0, std::size_t k0,
          std::size_t kb, double* dst) {
    std::size_t valid = std::min(kTile, rows - r0);
    for (std::size_t i = 0; i < kTile; ++i) {
        if (i < valid) {
            const double* src = z + (r0 + i) * cols + k0;
            for (std::size_t k = 0; k < kb; ++k) {
                dst[k * kTile + i] = src[k];
            }
        } else {
            for (std::size_t k = 0; k < kb; ++k) {
                dst[k * kTile + i] = 0.0;
            }
        }
    }
}

}  // namespace

void correlation_matrix(const double* data, std::size_t rows, std::size_t cols, double* out,
                        int threads) {
    if (rows == 0) {
        return;
    }

    // standardize each row to zero mean and unit length, so the correlation of
    // two rows is just their dot product. a flat row has no scale: it becomes
    // all-nan, which poisons every pair it appears in (numpy.corrcoef does the same)
    std::vector<double> z(rows * cols);
    for (std::size_t i = 0; i < rows; ++i) {
        const double* ri = data + i * cols;
        double* zi = z.data() + i * cols;
        double sum = 0.0;
        for (std::size_t k = 0; k < cols; ++k) {
            sum += ri[k];
        }
        double mean = cols ? sum / static_cast<double>(cols) : 0.0;
        double ss = 0.0;
        for (std::size_t k = 0; k < cols; ++k) {
            double d = ri[k] - mean;
            zi[k] = d;
            ss += d * d;
        }
        if (ss == 0.0) {
            std::fill(zi, zi + cols, std::numeric_limits<double>::quiet_NaN());
        } else {
            double inv = 1.0 / std::sqrt(ss);
            for (std::size_t k = 0; k < cols; ++k) {
                zi[k] *= inv;
            }
        }
    }

    // one task per upper-triangle tile pair. each task owns its output cells (and
    // their mirror), and always accumulates panels in the same order, so the
    // result does not depend on how tasks are scheduled.
    const std::size_t n_tiles = (rows + kTile - 1) / kTile;
    std::vector<std::pair<std::size_t, std::size_t>> tasks;
    for (std::size_t ti = 0; ti < n_tiles; ++ti) {
        for (std::size_t tj = ti; tj < n_tiles; ++tj) {
            tasks.emplace_back(ti, tj);
        }
    }

    // not worth waking threads for tiny problems
    const double work = static_cast<double>(rows) * static_cast<double>(rows) *
                        static_cast<double>(cols);
    int use_threads = threads;
    if (work < 2e6) {
        use_threads = 1;
    } else if (threads < 0) {
        // auto: about 4M multiply-adds per thread amortizes the thread start-up
        use_threads = static_cast<int>(std::max(1.0, std::min(work / 4e6, static_cast<double>(std::max(1u, std::thread::hardware_concurrency())))));
    }
    const PanelKernel kernel = select_kernel();

    parallel_for(tasks.size(), use_threads, [&](std::size_t t) {
        std::size_t i0 = tasks[t].first * kTile;
        std::size_t j0 = tasks[t].second * kTile;
        alignas(64) double acc[kTile * kTile] = {};
        std::vector<double> pa(kPanel * kTile), pb(kPanel * kTile);
        for (std::size_t k0 = 0; k0 < cols; k0 += kPanel) {
            std::size_t kb = std::min(kPanel, cols - k0);
            pack(z.data(), rows, cols, i0, k0, kb, pa.data());
            pack(z.data(), rows, cols, j0, k0, kb, pb.data());
            kernel(pa.data(), pb.data(), kb, acc);
        }
        std::size_t ni = std::min(kTile, rows - i0), nj = std::min(kTile, rows - j0);
        for (std::size_t i = 0; i < ni; ++i) {
            for (std::size_t j = 0; j < nj; ++j) {
                double corr = acc[i * kTile + j];
                if (corr > 1.0) {
                    corr = 1.0;
                } else if (corr < -1.0) {
                    corr = -1.0;
                }
                out[(i0 + i) * rows + j0 + j] = corr;
                out[(j0 + j) * rows + i0 + i] = corr;
            }
        }
    });
}

}  // namespace quantly
