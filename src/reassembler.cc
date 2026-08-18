#include "reassembler.hh"
#include "debug.hh"

using namespace std;

// void Reassembler::insert( uint64_t first_index, string data, bool is_last_substring )
// {
//   // debug( "unimplemented insert({}, {}, {}) called", first_index, data, is_last_substring );
//   Writer& writer = output_.writer();

//   uint64_t max_index = next_idx_ + writer.available_capacity();
//   for (uint64_t i = 0; i < data.length(); i++) {
//     uint64_t idx = first_index + i;
//     if (first_index + i < next_idx_ || first_index + i >= max_index) continue;
//     // mp_[first_index + i] = data[i];
//     mp_.try_emplace( idx, data[i] );

//   }
//   if (is_last_substring) {
//     last_idx_ = first_index + data.length();
//     has_last_ = 1;
//   }
//   string s;
//   while(1) {
//     auto it = mp_.find(next_idx_);
//     if (it == mp_.end()) break;
//     s += it->second;
//     mp_.erase(it);
//     next_idx_++;
//   }
//   // if (!s.empty())
//     writer.push(s);
//   if (has_last_ && next_idx_ == last_idx_) writer.close();

 
// }

void Reassembler::insert( uint64_t first_index, string data, bool is_last_substring )
{
  // debug( "unimplemented insert({}, {}, {}) called", first_index, data, is_last_substring );
  Writer& writer = output_.writer();

  uint64_t last_unacceptable = next_idx_ + writer.available_capacity();
  for (uint64_t i = 0; i < data.length(); i++) {
    uint64_t idx = first_index + i;
    if (idx < next_idx_) continue;
    if (idx >= last_unacceptable) break;
    uint64_t position = idx % capacity_;
    if (is_ready_[position]) continue;
    pending_[position] = data[i];
    is_ready_[position] = true;
    count_bytes_pending_++;
  }

  if (is_last_substring) {
    last_idx_ = first_index + data.length();
    has_last_ = 1;
  }
  string s;
  while(next_position_ < capacity_ && is_ready_[next_position_]) {
    s += pending_[next_position_];
    is_ready_[next_position_] = false;
    count_bytes_pending_--;
    next_idx_++;
    next_position_++;
    next_position_ %= capacity_;
  }
  // if (!s.empty())
  writer.push(s);
  if (has_last_ && next_idx_ == last_idx_) writer.close();

 
}
// idx可能超过u64范围



// }
// How many bytes are stored in the Reassembler itself?
// This function is for testing only; don't add extra state to support it.
uint64_t Reassembler::count_bytes_pending() const
{
  // debug( "unimplemented count_bytes_pending() called" );
  return count_bytes_pending_;
}
