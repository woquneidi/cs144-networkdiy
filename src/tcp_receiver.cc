#include "tcp_receiver.hh"
#include "debug.hh"

using namespace std;

void TCPReceiver::receive( TCPSenderMessage message )
{
  // Your code here.
  // debug( "unimplemented receive() called" );
  // (void)message;
  if (message.RST) {
    reassembler_.reader().set_error();
    return;
  }
  if (!isn_.has_value()) {
    if (!message.SYN) return;
    isn_ = message.seqno;
  }
  uint64_t first_index = message.seqno.unwrap(isn_.value(), reassembler_.writer().bytes_pushed() + 1) + message.SYN - 1;

  reassembler_.insert(first_index, move(message.payload), message.FIN);
}
// rst为1时在bytestream中seterror
// 计算firstindex 可以利用SYN

TCPReceiverMessage TCPReceiver::send() const
{
  // Your code here.
  // debug( "unimplemented send() called" );
  TCPReceiverMessage message;
  auto& writer = reassembler_.writer();
  if (isn_.has_value()) {
    message.ackno = isn_.value() + 1 + writer.bytes_pushed() + writer.is_closed();
  }
  message.window_size = (uint16_t)min<uint64_t>(writer.available_capacity(), UINT16_MAX);
  message.RST = writer.has_error();
  
  return message;
}
// 计算windowssize  是16位 要取min
