#!/usr/bin/env python3

from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from threading import *
from random import randint
import time
import random

def switchy_main(net,**kwargs):

    print('rcsv args:',kwargs)

    my_intf = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_intf]
    myips = [intf.ipaddr for intf in my_intf]
    print("comming kwargs=",kwargs)
    while True:
        gotpkt = True
        try:
            timestamp,dev,pkt = net.recv_packet()
            log_debug("Device is {}".format(dev))
        except NoPackets:
            log_debug("No packets available in recv_packet")
            gotpkt = False
        except Shutdown:
            log_debug("Got shutdown signal")
            break

        if gotpkt:
            log_debug("I got a packet {}".format(pkt))

        if dev == "middlebox-eth0":
            log_debug("Received from blaster")
            '''
            Received data packet
            Should I drop it?
            If not, modify headers & send to blastee
            '''
            luck=random.random()
            if luck <= kwargs.dropRate:
                log_info(":( sorry to inform you that your packet was 'accidentlly' lost")
                continue
            else:
                log_info("U are a lucky basterd")
                pkt[Ethernet].src,pkt[Ethernet].dst=net.interface_by_name("middlebox-eth1").ethaddr,EthAddr("20:00:00:00:00:01")
                pkt[IPv4].ttl-=1
                net.send_packet("middlebox-eth1", pkt)
        elif dev == "middlebox-eth1":
            log_debug("Received from blastee")
            '''
            Received ACK
            Modify headers & send to blaster. Not dropping ACK packets!
            net.send_packet("middlebox-eth0", pkt)
            '''
            pkt[Ethernet].src,pkt[Ethernet].dst=net.interface_by_name("middlebox-eth0").ethaddr,EthAddr("10:00:00:00:00:01")
            pkt[IPv4].ttl-=1
            net.send_packet("middlebox-eth0", pkt)
        else:
            log_debug("Oops :))")

    net.shutdown()
