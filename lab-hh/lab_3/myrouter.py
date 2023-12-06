#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *

class TableRow:
    def __init__(self,prefix,mask,nextHop,portName):
        self.prefix=prefix
        self.mask=mask
        self.nextHop=nextHop        
        self.portName=portName


# 核心是想明白如何把来数据包的ip与表项逐项比对寻找出最长前缀匹配，
# python内置有 IPv4Network IPv4Address对象
# 前者用于整合ip地址和mask，快捷得出mask位数；后者用于与int()结合快速掩码ip，并进行ip比对
# 那么比对流程就是循环每个 TableRow,逐个寻找符合最长前缀匹配的表项，若符合再比较掩码位数，
# 记住并更新最长前缀匹配表项index。不存在则为初始值-1

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
