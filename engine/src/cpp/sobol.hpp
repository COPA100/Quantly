#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace quantly {

// 32-bit sobol sequence with joe-kuo (new-joe-kuo-6.21201) direction numbers.
// points are indexed directly, so any slice of the sequence can be generated
// independently (used for threading).
constexpr int kSobolMaxDim = 30;

class Sobol {
public:
    explicit Sobol(int dims);  // throws std::invalid_argument outside [1, kSobolMaxDim]

    int dims() const { return dims_; }

    // fill out[0..dims) with the 32-bit integer coordinates of point `index`
    void point(std::uint64_t index, std::uint32_t* out) const;

    // advance `state` from point `index` to point `index + 1` (gray-code update)
    void next(std::uint64_t index, std::uint32_t* state) const;

private:
    int dims_;
    std::vector<std::uint32_t> v_;  // dims x 32 direction numbers
};

}  // namespace quantly
