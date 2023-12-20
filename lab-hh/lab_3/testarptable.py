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

        # 会学习的arp表
        arpTable={}
        for port in self.portsList:
            arpTable[port.ipaddr]=port.ethaddr
        self.arpTable=arpTable

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        timestamp, ifName, packet = recv
        log_info(f'rscv packet {packet} in {ifName}\n')
        # TODO: your logic here
        # arpTable={}
        arp = packet.get_header(Arp)
        if arp:
            self.arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            log_info(f'cur arptable:{self.arpTable} \n')

            # for key,val in self.arpTable.items():
            #     print(key,' arp pair ',val)
            # for port in self.portsList:
            if self.arpTable[arp.targetprotoaddr]:
                rePacket = Ethernet()
                rePacket.src = self.arpTable[arp.targetprotoaddr]
                rePacket.dst = arp.senderhwaddr
                rePacket.ethertype = EtherType.ARP
                rePacket+=Arp(
                    #reply type
                    operation=ArpOperation.Reply,
                    #router port ethaddr
                    senderhwaddr=self.arpTable[arp.targetprotoaddr],
                    #router port ip
                    senderprotoaddr=arp.targetprotoaddr,
                    #original arp request hwaddr
                    targethwaddr=arp.senderhwaddr,
                    #original arp request ipaddr
                    targetprotoaddr= arp.senderprotoaddr)
                print(f'sending repacket:{rePacket}\n')
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
