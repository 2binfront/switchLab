#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *


class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        # other initialization stuff here
        self.portsList=net.interfaces()

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        timestamp, ifName, packet = recv
        # TODO: your logic here
        arpTable={}
        arp = packet.get_header(Arp)
        if arp:
            arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            log_info(f'cur arptable:{arpTable} \n')

            for key,val in arpTable.items():
                print(key,' arp pair ',val)
            for port in self.portsList:
                if arp.targetprotoaddr == port.ipaddr:
                    rePacket = Ethernet()
                    rePacket.src = port.ethaddr
                    rePacket.dst = arp.senderhwaddr
                    rePacket.ethertype = EtherType.ARP
                    rePacket+=Arp(
                        #reply type
                        operation=ArpOperation.Reply,
                        #router port ethaddr
                        senderhwaddr=port.ethaddr,
                        #router port ip
                        senderprotoaddr=port.ipaddr,
                        #original arp request hwaddr
                        targethwaddr=arp.senderhwaddr,
                        #original arp request ipaddr
                        targetprotoaddr= arp.senderprotoaddr)
                    self.net.send_packet(ifName,rePacket)


    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
            except NoPackets:
                continue
            except Shutdown:
                break

            self.handle_packet(recv)

        self.stop()

    def stop(self):
        self.net.shutdown()


def main(net):
    '''
    Main entry point for router.  Just create Router
    object and get it going.
    '''
    router = Router(net)
    router.start()
