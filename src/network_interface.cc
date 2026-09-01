#include <iostream>

#include "arp_message.hh"
#include "debug.hh"
#include "ethernet_frame.hh"
#include "exception.hh"
#include "helpers.hh"
#include "network_interface.hh"

using namespace std;

//! \param[in] ethernet_address Ethernet (what ARP calls "hardware") address of the interface
//! \param[in] ip_address IP (what ARP calls "protocol") address of the interface
NetworkInterface::NetworkInterface( string_view name,
                                    shared_ptr<OutputPort> port,
                                    const EthernetAddress& ethernet_address,
                                    const Address& ip_address )
  : name_( name )
  , port_( notnull( "OutputPort", move( port ) ) )
  , ethernet_address_( ethernet_address )
  , ip_address_( ip_address )
{
  cerr << "DEBUG: Network interface has Ethernet address " << to_string( ethernet_address_ ) << " and IP address "
       << ip_address.ip() << "\n";
}

//! \param[in] dgram the IPv4 datagram to be sent
//! \param[in] next_hop the IP address of the interface to send it to (typically a router or default gateway, but
//! may also be another host if directly connected to the same network as the destination) Note: the Address type
//! can be converted to a uint32_t (raw 32-bit IP address) by using the Address::ipv4_numeric() method.
void NetworkInterface::send_datagram( const InternetDatagram& dgram, const Address& next_hop )
{
  // debug( "unimplemented send_datagram called" );
  // (void)dgram;
  // (void)next_hop;
  uint32_t next_ip = next_hop.ipv4_numeric();
  EthernetFrame frame;
  if (arp_cache_.count(next_ip)) {
    frame.header.src = ethernet_address_;
    frame.header.dst = arp_cache_[next_ip].ethernet_address;
    frame.header.type = EthernetHeader::TYPE_IPv4;
    frame.payload = serialize(dgram);
    transmit(frame);
  } else {
    if (pending_.count(next_ip)) {
      pending_[next_ip].datagrams.push_back(dgram);
      return;
    }

    ARPMessage arp;
    arp.opcode = ARPMessage::OPCODE_REQUEST;
    arp.sender_ethernet_address = ethernet_address_;
    arp.sender_ip_address = ip_address_.ipv4_numeric();
    arp.target_ip_address = next_ip;
    frame.header.src = ethernet_address_;
    frame.header.dst = ETHERNET_BROADCAST;
    frame.header.type = EthernetHeader::TYPE_ARP;
    frame.payload = serialize(arp);
    pending_[next_ip].datagrams.push_back(dgram);
    transmit(frame);
  }
}

//! \param[in] frame the incoming Ethernet frame
void NetworkInterface::recv_frame( EthernetFrame frame )
{
  // debug( "unimplemented recv_frame called" );
  // (void)frame;
  EthernetAddress dst = frame.header.dst;
  if (dst != ETHERNET_BROADCAST && dst != ethernet_address_) return;
  if (frame.header.type == EthernetHeader::TYPE_IPv4) {
    InternetDatagram dgram;
    if (!parse(dgram, frame.payload)) return;
    datagrams_received_.push(dgram);
  }
  if (frame.header.type == EthernetHeader::TYPE_ARP) {
    ARPMessage arp;
    if (!parse(arp, frame.payload)) return;
    arp_cache_[arp.sender_ip_address].ethernet_address = arp.sender_ethernet_address;
    arp_cache_[arp.sender_ip_address].age_ms = 0;
    for (auto dgram : pending_[arp.sender_ip_address].datagrams) {
      uint32_t next_ip = arp.sender_ip_address;
      EthernetFrame frame2;
      frame2.header.src = ethernet_address_;
      frame2.header.dst = arp_cache_[next_ip].ethernet_address;
      frame2.header.type = EthernetHeader::TYPE_IPv4;
      frame2.payload = serialize(dgram);
      transmit(frame2);
    }
    pending_.erase(arp.sender_ip_address);

    if (arp.opcode == ARPMessage::OPCODE_REQUEST && arp.target_ip_address == ip_address_.ipv4_numeric()) {
      EthernetFrame frame2;
      frame2.header.type = EthernetHeader::TYPE_ARP;
      frame2.header.src = ethernet_address_;
      frame2.header.dst = arp.sender_ethernet_address;
      ARPMessage arp2;
      arp2.opcode = ARPMessage::OPCODE_REPLY;
      arp2.sender_ethernet_address = ethernet_address_;
      arp2.sender_ip_address = ip_address_.ipv4_numeric();
      arp2.target_ethernet_address = arp.sender_ethernet_address;
      arp2.target_ip_address = arp.sender_ip_address;
      frame2.payload = serialize(arp2);
      transmit(frame2);
    }

  }
}

//! \param[in] ms_since_last_tick the number of milliseconds since the last call to this method
void NetworkInterface::tick( const size_t ms_since_last_tick )
{
  // debug( "unimplemented tick({}) called", ms_since_last_tick );
  for (auto it = arp_cache_.begin(); it != arp_cache_.end(); ){
    it->second.age_ms += ms_since_last_tick;
    if (it -> second.age_ms >= 30000) {
      it = arp_cache_.erase(it);
    } else {
      it++;
    }
  } 
  for (auto it = pending_.begin(); it != pending_.end(); ) {
    it->second.age_ms += ms_since_last_tick;
    if (it -> second.age_ms >= 5000) {
      it = pending_.erase(it);
    } else {
      it++;
    }
  }
}
