#!/usr/bin/env python3

from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from threading import *
import time


def switchy_main(net,**kwargs):
    """_summary_
<------- Switchyard headers -----> <----- Your packet header(raw bytes) ------> <-- Payload in raw bytes --->
-------------------------------------------------------------------------------------------------------------
|  ETH Hdr |  IP Hdr  |  UDP Hdr  |          Sequence number(32 bits)          |      Payload  (8 bytes)    |
-------------------------------------------------------------------------------------------------------------
    my packet header and payload are put into one RawPacketContents header
    Args:
        net (_type_): _description_
    """
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]
    print(kwargs)
    blasterIp,num=kwargs['blasterIp'],int(kwargs['num'])
    while True:
        try:
            timestamp,dev,pkt = net.recv_packet()
            log_debug("Device is {}".format(dev))
        except NoPackets:
            log_debug("No packets available in recv_packet")
            continue
        except Shutdown:
            log_debug("Got shutdown signal")
            break
        else:
            log_debug("I got a packet from {}".format(dev))
            log_debug("Pkt: {}".format(pkt))
            
            seqAns=pkt[3].to_bytes()[0:4]
            payloadAns=pkt[3].to_bytes()[6:]
            rePkt=Ethernet(src=dev.ethaddr,dst=pkt[Ethernet].src,ethertype=EtherType.IPv4)+\
                IPv4(protocol=IPProtocol.UDP,src=dev.ipaddr,dst=blasterIp)+UDP()+\
                seqAns+payloadAns
            net.send_packet(dev,rePkt)



    net.shutdown()
