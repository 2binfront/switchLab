#!/usr/bin/env python3

from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from threading import *
import time

def switchy_main(net,**kwargs):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]
    blasterIp=kwargs.blasterIp
    num=kwargs.num
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
            seqRaw,lenRaw=struct.unpack("!IH",pkt[-2].tobytes())
            ackPayload=pkt[-1].tobytes()
            rePkt=Ethernet(src=dev.ethaddr,dst=pkt[Ethernet].src,ethertype=EtherType.IPv4)+\
                IPv4(protocol=IPProtocol.UDP,src=dev.ipaddr,dst=blasterIp)+UDP()+\
                pkt[-2].tobytes()[:4]+ackPayload[:8]
            net.send_packet(dev,rePkt)



    net.shutdown()
