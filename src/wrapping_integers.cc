#include "wrapping_integers.hh"
#include "debug.hh"
#include <cassert>
using namespace std;

Wrap32 Wrap32::wrap( uint64_t n, Wrap32 zero_point )
{
  // Your code here.
  // debug( "unimplemented wrap( {}, {} ) called", n, zero_point.raw_value_ );
  return zero_point + (uint32_t)n;
}

uint64_t Wrap32::unwrap( Wrap32 zero_point, uint64_t checkpoint ) const
{
  // Your code here.
  // debug( "unimplemented unwrap( {}, {} ) called", zero_point.raw_value_, checkpoint );
  uint32_t gap = raw_value_ - zero_point.raw_value_;
  long long mid = checkpoint / (1ull << 32);
  uint64_t l = max(0ll, mid - 1), r = min(mid + 1, (1ll << 32) - 1);
  assert(r - l <= 2);
  uint64_t res = mid * (1ull << 32) + gap;
  for (uint64_t i = l; i <= r; i++) {
    uint64_t tmp = (1ull << 32) * i + gap;
    if (max(tmp, checkpoint) - min(tmp, checkpoint) < max(res, checkpoint) - min(res, checkpoint)) res = tmp;
  }
  return res;
}
