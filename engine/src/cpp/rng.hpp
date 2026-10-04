#pragma once

#include <cstddef>
#include <cstdint>

namespace quantly {

// philox4x32-10 (salmon et al., random123): a counter-based rng. the output is a
// pure function of (key, counter), so any block of a simulation can be generated
// independently and in any order, which is what makes threaded runs reproducible.
// `count` independent counters are processed together in structure-of-arrays form
// so the ten rounds are plain loops the compiler can vectorize.
inline void philox4x32_10(std::uint32_t k0, std::uint32_t k1, std::uint32_t* c0,
                          std::uint32_t* c1, std::uint32_t* c2, std::uint32_t* c3,
                          std::size_t count) {
    constexpr std::uint32_t M0 = 0xD2511F53u, M1 = 0xCD9E8D57u;
    constexpr std::uint32_t W0 = 0x9E3779B9u, W1 = 0xBB67AE85u;
    for (int round = 0; round < 10; ++round) {
        for (std::size_t i = 0; i < count; ++i) {
            std::uint64_t p0 = static_cast<std::uint64_t>(M0) * c0[i];
            std::uint64_t p1 = static_cast<std::uint64_t>(M1) * c2[i];
            std::uint32_t n0 = static_cast<std::uint32_t>(p1 >> 32) ^ c1[i] ^ k0;
            std::uint32_t n1 = static_cast<std::uint32_t>(p1);
            std::uint32_t n2 = static_cast<std::uint32_t>(p0 >> 32) ^ c3[i] ^ k1;
            std::uint32_t n3 = static_cast<std::uint32_t>(p0);
            c0[i] = n0;
            c1[i] = n1;
            c2[i] = n2;
            c3[i] = n3;
        }
        k0 += W0;
        k1 += W1;
    }
}

}  // namespace quantly
