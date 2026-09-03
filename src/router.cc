#include "router.hh"
#include "debug.hh"

#include <iostream>

using namespace std;

// route_prefix: The "up-to-32-bit" IPv4 address prefix to match the datagram's destination address against
// prefix_length: For this route to be applicable, how many high-order (most-significant) bits of
//    the route_prefix will need to match the corresponding bits of the datagram's destination address?
// next_hop: The IP address of the next hop. Will be empty if the network is directly attached to the router (in
//    which case, the next hop address should be the datagram's final destination).
// interface_num: The index of the interface to send the datagram out on.
void Router::add_route( const uint32_t route_prefix,
                        const uint8_t prefix_length,
                        const optional<Address> next_hop,
                        const size_t interface_num )
{
  // cerr << "DEBUG: adding route " << Address::from_ipv4_numeric( route_prefix ).ip() << "/"
      //  << static_cast<int>( prefix_length ) << " => " << ( next_hop.has_value() ? next_hop->ip() : "(direct)" )
      //  << " on interface " << interface_num << "\n";

  // debug( "unimplemented add_route() called" );
  uint32_t mask = 0xffffffffu;
  if (prefix_length == 0) {
    mask = 0;
  } else {
    mask <<= 32 - prefix_length;
  }
  uint32_t route_prefix_mask = (route_prefix & mask);
  route_table_[prefix_length][route_prefix_mask] = {interface_num, next_hop};
}

// Go through all the interfaces, and route every incoming datagram to its proper outgoing interface.
void Router::route()
{
  // debug( "unimplemented route() called" );
  for (size_t interface_num = 0; interface_num < interfaces_.size(); interface_num++) {
    queue<InternetDatagram> &datagrams_received_ = interface(interface_num) -> datagrams_received();
    while (!datagrams_received_.empty()) {
      InternetDatagram dgram = datagrams_received_.front();
      datagrams_received_.pop();
      uint32_t mask = 0xffffffffu;
      for (int i = 32; i >= 0; i--) {
        uint32_t dst_ip_mask = (dgram.header.dst & mask);
        if (route_table_[i].count(dst_ip_mask)) {
          if (dgram.header.ttl <= 1) {
            break;
          }
          dgram.header.ttl--;
          dgram.header.compute_checksum();
          auto [next_interface_num, next_hop] = route_table_[i][dst_ip_mask];
          if (!next_hop.has_value()) {
            next_hop = Address::from_ipv4_numeric(dgram.header.dst);
          }
          interface(next_interface_num) -> send_datagram(dgram, next_hop.value());
          break;
        }
        mask <<= 1;
      }
    }
  }
}
//ttl应该先判断再减
//compute_checksum