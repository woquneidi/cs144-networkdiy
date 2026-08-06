#include "byte_stream.hh"

using namespace std;

ByteStream::ByteStream( uint64_t capacity ) : capacity_( capacity ) {}

void Writer::push( string data )
{
  // (void)data; // Your code here.
  if (is_closed()) return;
  uint64_t len = data.length();
  uint64_t canpush = min(len, available_capacity());
  buffer_.append(data, 0, canpush);
  bytes_pushed_ += canpush;
}

void Writer::close()
{
  writer_closed_ = true;
  // Your code here.
}

bool Writer::is_closed() const
{
  return writer_closed_; // Your code here.
}

uint64_t Writer::available_capacity() const
{
  return capacity_ - buffer_.length(); // Your code here.
}

uint64_t Writer::bytes_pushed() const
{
  return bytes_pushed_; // Your code here.
}

string_view Reader::peek() const
{
  return buffer_;
}

void Reader::pop( uint64_t len )
{
  // (void)len; // Your code here.
  uint64_t pop_len = min(len, bytes_buffered());
  buffer_.erase(0, pop_len);
  bytes_popped_ += pop_len;
}

bool Reader::is_finished() const
{
  if (!bytes_buffered() && writer_closed_) return true;
  return false;
}

uint64_t Reader::bytes_buffered() const
{
  return buffer_.length(); // Your code here.
}

uint64_t Reader::bytes_popped() const
{
  return bytes_popped_; // Your code here.
}
