#include "reassembler.hh"
#include "debug.hh"

using namespace std;

void Reassembler::insert( uint64_t first_index, string data, bool is_last_substring )
{
  // debug( "unimplemented insert({}, {}, {}) called", first_index, data, is_last_substring );
  uint64_t max_index = next_idx_ + output_.writer().available_capacity();
  for (uint64_t i = 0; i < (uint64_t)data.length(); i++) {
    uint64_t idx = first_index + i;
    if (first_index + i < next_idx_ || first_index + i >= max_index || mp_.count(idx)) continue;
    mp_[first_index + i] = data[i];
  }
  if (is_last_substring) {
    last_idx_ = first_index + data.length();
    has_last_ = 1;
  }
  string s;
  while(mp_.count(next_idx_)) {
    if ( output_.writer().available_capacity() == 0 ) {
      break;
    }
    s += mp_[next_idx_];
    mp_.erase(next_idx_);
    next_idx_++;
  }
  output_.writer().push(s);
  if (has_last_ && next_idx_ == last_idx_) output_.writer().close();

 
}

// How many bytes are stored in the Reassembler itself?
// This function is for testing only; don't add extra state to support it.
uint64_t Reassembler::count_bytes_pending() const
{
  // debug( "unimplemented count_bytes_pending() called" );
  return mp_.size();
}
