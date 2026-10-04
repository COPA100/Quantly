#include "sobol.hpp"

#include <stdexcept>

namespace quantly {

namespace {

struct Params {
    int s;          // polynomial degree
    unsigned a;     // polynomial coefficients
    unsigned m[7];  // initial direction numbers
};

// dimensions 2..30 of new-joe-kuo-6.21201 (dimension 1 is van der corput)
const Params kParams[kSobolMaxDim - 1] = {
    {1, 0, {1}},
    {2, 1, {1, 3}},
    {3, 1, {1, 3, 1}},
    {3, 2, {1, 1, 1}},
    {4, 1, {1, 1, 3, 3}},
    {4, 4, {1, 3, 5, 13}},
    {5, 2, {1, 1, 5, 5, 17}},
    {5, 4, {1, 1, 5, 5, 5}},
    {5, 7, {1, 1, 7, 11, 19}},
    {5, 11, {1, 1, 5, 1, 1}},
    {5, 13, {1, 1, 1, 3, 11}},
    {5, 14, {1, 3, 5, 5, 31}},
    {6, 1, {1, 3, 3, 9, 7, 49}},
    {6, 13, {1, 1, 1, 15, 21, 21}},
    {6, 16, {1, 3, 1, 13, 27, 49}},
    {6, 19, {1, 1, 1, 15, 7, 5}},
    {6, 22, {1, 3, 1, 15, 13, 25}},
    {6, 25, {1, 1, 5, 5, 19, 61}},
    {7, 1, {1, 3, 7, 11, 23, 15, 103}},
    {7, 4, {1, 3, 7, 13, 13, 15, 69}},
    {7, 7, {1, 1, 3, 13, 7, 35, 63}},
    {7, 8, {1, 3, 5, 9, 1, 25, 53}},
    {7, 14, {1, 3, 1, 13, 9, 35, 107}},
    {7, 19, {1, 3, 1, 5, 27, 61, 31}},
    {7, 21, {1, 1, 5, 11, 19, 41, 61}},
    {7, 28, {1, 3, 5, 3, 3, 13, 69}},
    {7, 31, {1, 1, 7, 13, 1, 19, 1}},
    {7, 32, {1, 3, 7, 5, 13, 19, 59}},
    {7, 37, {1, 1, 3, 9, 9, 25, 99}},
};

}  // namespace

Sobol::Sobol(int dims) : dims_(dims) {
    if (dims < 1 || dims > kSobolMaxDim) {
        throw std::invalid_argument("sobol supports 1 to 30 dimensions");
    }
    v_.assign(static_cast<std::size_t>(dims) * 32, 0);
    for (int i = 0; i < 32; ++i) {
        v_[static_cast<std::size_t>(i)] = 1u << (31 - i);
    }
    for (int d = 1; d < dims; ++d) {
        const Params& p = kParams[d - 1];
        std::uint32_t* v = &v_[static_cast<std::size_t>(d) * 32];
        for (int i = 0; i < p.s; ++i) {
            v[i] = p.m[i] << (31 - i);
        }
        for (int i = p.s; i < 32; ++i) {
            v[i] = v[i - p.s] ^ (v[i - p.s] >> p.s);
            for (int k = 1; k < p.s; ++k) {
                if ((p.a >> (p.s - 1 - k)) & 1u) {
                    v[i] ^= v[i - k];
                }
            }
        }
    }
}

void Sobol::point(std::uint64_t index, std::uint32_t* out) const {
    std::uint64_t gray = index ^ (index >> 1);
    for (int d = 0; d < dims_; ++d) {
        const std::uint32_t* v = &v_[static_cast<std::size_t>(d) * 32];
        std::uint32_t x = 0;
        for (int bit = 0; bit < 32; ++bit) {
            if ((gray >> bit) & 1u) {
                x ^= v[bit];
            }
        }
        out[d] = x;
    }
}

void Sobol::next(std::uint64_t index, std::uint32_t* state) const {
    // the gray code flips the bit at the lowest zero of `index`
    int bit = 0;
    while ((index >> bit) & 1u) {
        ++bit;
    }
    for (int d = 0; d < dims_; ++d) {
        state[d] ^= v_[static_cast<std::size_t>(d) * 32 + static_cast<std::size_t>(bit)];
    }
}

}  // namespace quantly
