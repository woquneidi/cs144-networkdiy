#include "tcp_sender.hh"
#include "debug.hh"
#include "tcp_config.hh"

using namespace std;

// This function is for testing only; don't add extra state to support it.
uint64_t TCPSender::sequence_numbers_in_flight() const
{
  // debug( "unimplemented sequence_numbers_in_flight() called" );
  return sequence_numbers_in_flight_;
}

// This function is for testing only; don't add extra state to support it.
uint64_t TCPSender::consecutive_retransmissions() const
{
  // debug( "unimplemented consecutive_retransmissions() called" );
  return consecutive_retransmissions_;
}

void TCPSender::push( const TransmitFunction& transmit )
{
  // debug( "unimplemented push() called" );
  // (void)transmit;
  uint64_t effective_window = window_size_ == 0 ? 1 : window_size_;
  auto& input_reader = reader();
  while (effective_window > sequence_numbers_in_flight_ && !fin_sent_) {
    TCPSenderMessage message;

    uint64_t rest_size = effective_window - sequence_numbers_in_flight_;
    message.seqno = Wrap32::wrap(next_absolute_seqno_, isn_);
    if (!syn_sent_ && rest_size) {
      message.SYN = true;
      rest_size--;
    }
    uint64_t add_len = min<uint64_t>({rest_size, input_reader.bytes_buffered(), TCPConfig::MAX_PAYLOAD_SIZE});  
    message.payload = string(input_reader.peek().substr(0, add_len));
    input_reader.pop(add_len);
    rest_size -= add_len;
    if (!fin_sent_ && rest_size) {
      if (input_reader.is_finished()) {
        message.FIN = true;
      }
    }
    if (!message.sequence_length()) {
      break;
    }
    message.RST = input_.has_error();

    transmit(message);
    outstanding_.push_back(message);
    if (message.FIN) {
      fin_sent_ = true;
    }
    if (message.SYN) {
      syn_sent_ = true;
    }
    sequence_numbers_in_flight_ += message.sequence_length();
    next_absolute_seqno_ += message.sequence_length();
  }

}
//一直构造到和outstanding总共长度到windows_size 


TCPSenderMessage TCPSender::make_empty_message() const
{
  // debug( "unimplemented make_empty_message() called" );
  TCPSenderMessage message;
  message.seqno = Wrap32::wrap(next_absolute_seqno_, isn_);
  message.RST = input_.has_error();
  return message;
}

void TCPSender::receive( const TCPReceiverMessage& msg )
{
  // debug( "unimplemented receive() called" );
  // (void)msg;
  if (msg.RST) {
    input_.set_error();
    return;
  }
  uint64_t now_abs_ack;
  if (!msg.ackno.has_value()) {
    now_abs_ack = last_absolute_ack_;
  } else {
    now_abs_ack = msg.ackno.value().unwrap(isn_, next_absolute_seqno_);
  }
  window_size_ = msg.window_size;
  if (now_abs_ack > next_absolute_seqno_ || now_abs_ack <= last_absolute_ack_) return;
  wait_time_ = 0;
  consecutive_retransmissions_ = 0;
  current_RTO_ms_ = initial_RTO_ms_;

  while (!outstanding_.empty()) {
    auto& front_message = outstanding_.front();
    uint64_t unsave_abs_sno = front_message.seqno.unwrap(isn_, next_absolute_seqno_) + front_message.sequence_length();
    if (unsave_abs_sno > now_abs_ack) break;
    sequence_numbers_in_flight_ -= front_message.sequence_length();
    outstanding_.pop_front();
  }
  last_absolute_ack_ = now_abs_ack;
}
//没有ackno时也要更新window_size
void TCPSender::tick( uint64_t ms_since_last_tick, const TransmitFunction& transmit )
{
  // debug( "unimplemented tick({}, ...) called", ms_since_last_tick );
  // (void)transmit;
  if ( outstanding_.empty() ) {
    return;
  }
  wait_time_ += ms_since_last_tick;
  if (wait_time_ >= current_RTO_ms_) {
    wait_time_ = 0;
    transmit(outstanding_.front());
    if (window_size_ != 0) {
      current_RTO_ms_ *= 2;
      consecutive_retransmissions_++;
    }
  }
}
//outstanding_.empty时直接return
// window_size_ != 0时不认为丢包重传
