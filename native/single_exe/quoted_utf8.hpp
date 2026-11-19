// ConPTY receives UTF-8 and exposes UTF-16 keyboard input. XTerm's 2005 mode
// quotes each encoded octet, so a quoted non-ASCII scalar is no longer UTF-8.
// Keep the first literal-next and recognize only a complete, minimally encoded
// scalar with that same ASCII prefix on *every* continuation. No valid UTF-8
// byte stream can contain this interleaving. All other bytes stay verbatim.
#pragma once

#include <array>
#include <cassert>
#include <cstddef>
#include <cstring>
#include <string_view>

namespace nemo {
class QuotedUtf8Input {
public:
    static constexpr std::size_t capacity = 4096;
    char* input() noexcept { return _buffer.data() + _tail.size(); }

    std::string_view consume(std::size_t count, bool armed) noexcept
    {
        assert(count <= capacity);
        if (!armed && !_held) {
            _previous = 256;
            return {input(), count};
        }
        char* begin = input() - _held;
        std::memcpy(begin, _tail.data(), _held);
        _held = 0;
        const char* src = begin;
        const char* end = input() + count;
        char* dst = begin;
        while (src != end) {
            const auto lead = static_cast<unsigned char>(*src);
            const unsigned width = lead >= 0xc2 && lead <= 0xdf ? 2 :
                                   lead >= 0xe0 && lead <= 0xef ? 3 :
                                   lead >= 0xf0 && lead <= 0xf4 ? 4 : 0;
            if (width && _previous < 128) {
                const auto available = static_cast<std::size_t>(end - src);
                unsigned i = 1;
                for (; i < width; ++i) {
                    const auto mark = 2*i - 1;
                    if (available <= mark) break;
                    if (static_cast<unsigned char>(src[mark]) != _previous) { i = 0; break; }
                    if (available == mark + 1) break;
                    const auto byte = static_cast<unsigned char>(src[mark + 1]);
                    if (byte < 0x80 || byte > 0xbf || (i == 1 &&
                        ((lead == 0xe0 && byte < 0xa0) || (lead == 0xed && byte > 0x9f) ||
                         (lead == 0xf0 && byte < 0x90) || (lead == 0xf4 && byte > 0x8f)))) {
                        i = 0; break;
                    }
                }
                if (i == width) {
                    // The caller already received the first prefix, even if it
                    // arrived on its own (a lone Ctrl+V must never wait).
                    for (unsigned j = 0; j < width; ++j) *dst++ = src[2*j];
                    _previous = static_cast<unsigned char>(dst[-1]);
                    src += 2*width - 1;
                    continue;
                }
                if (i) {
                    // Only the lead and up to five following octets can be
                    // pending. Do not delete anything from an incomplete pair.
                    _held = available;
                    std::memcpy(_tail.data(), src, _held);
                    break;
                }
            }
            _previous = lead;
            *dst++ = *src++;
        }
        return {begin, static_cast<std::size_t>(dst - begin)};
    }

    std::string_view finish() noexcept
    {
        const auto bytes = _held;
        _held = 0;
        _previous = 256;
        return {_tail.data(), bytes};
    }

private:
    std::array<char, capacity + 6> _buffer;
    std::array<char, 6> _tail;
    std::size_t _held = 0;
    unsigned _previous = 256;
};
} // namespace nemo
