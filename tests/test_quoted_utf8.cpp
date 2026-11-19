// Byte-level boundary checks for the bundled host's Unicode conversion.
#include "../native/single_exe/quoted_utf8.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string>

using namespace std::literals;
using Decoder = nemo::QuotedUtf8Input;
static std::string take(Decoder& d, std::string_view part, bool enabled = true)
{
    if (part.size() > d.capacity) std::abort();
    std::memcpy(d.input(), part.data(), part.size());
    return std::string(d.consume(part.size(), enabled));
}
static void check(std::string_view actual, std::string_view expected)
{
    if (actual != expected) { std::fprintf(stderr, "unexpected %zu bytes (expected %zu)\n", actual.size(), expected.size()); std::abort(); }
}
static std::string quoted(std::string_view bytes, char marker)
{
    std::string out; for (char c : bytes) {out += marker; out += c;} return out;
}
// Test every partition of a sample, including one byte per input completion.
static void partitions(const std::string& input, const std::string& expected, bool enabled = true)
{
    if (input.empty() || input.size() > 15) std::abort();
    for (unsigned mask=0; mask < (1u << (input.size()-1)); ++mask) {
        Decoder d; std::string out; std::size_t pos=0;
        for (std::size_t i=1; i<=input.size(); ++i) {
            if (i<input.size() && !(mask & (1u << (i-1)))) continue;
            out += take(d, std::string_view(input).substr(pos, i-pos), enabled); pos=i;
        }
        out += d.finish(); check(out, expected);
    }
}
int main()
{
    for (char marker : {'\026', '\035', '!', '\0'}) {
        for (std::string scalar : {"\xc2\x80", "\xdf\xbf", "\xe0\xa0\x80", "\xe4\xb8\xad", "\xed\x9f\xbf", "\xf0\x90\x80\x80", "\xf0\x9f\x98\x80", "\xf4\x8f\xbf\xbf"}) {
            std::string q=quoted(scalar,marker), prefix(1,marker);
            partitions(q,prefix+scalar); partitions(q,q,false);
            partitions(prefix+scalar+prefix,prefix+scalar+prefix);
            for (std::size_t n=1; n<q.size(); ++n) {auto truncated=q.substr(0,n);partitions(truncated,truncated);}
        }
        for (std::string invalid : {"\xc0\x80", "\xe0\x80\x80", "\xed\xa0\x80", "\xf0\x8f\xbf\xbf", "\xf4\x90\x80\x80", "\xff"}) {
            auto encoded=quoted(invalid,marker); partitions(encoded,encoded);
        }
        std::string interrupted=quoted("\xe4\xb8\xad",marker);interrupted[4]='X';partitions(interrupted,interrupted);
    }
    Decoder d; check(take(d,"\026"),"\026"); check(take(d,"A"),"A"); check(take(d,"\r"),"\r");
    std::string source,expected;
    for (unsigned i=0;i<4000;++i) {source+="A\xe4\xb8\xad"+quoted("\xf0\x9f\x98\x80",'\026');expected+="A\xe4\xb8\xad\026\xf0\x9f\x98\x80";}
    for (std::size_t step : {4096u,4095u,67u,1u}) {
        Decoder stream; std::string out;
        for(std::size_t i=0;i<source.size();i+=step) out+=take(stream,std::string_view(source).substr(i,step));
        out+=stream.finish();check(out,expected);
    }
    std::puts("Quoted paste: scalar boundaries, ordinary Unicode, malformed/truncated bytes and split reads passed");
}
