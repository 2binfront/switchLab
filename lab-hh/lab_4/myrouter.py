#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
import ipaddress
from switchyard.lib.userlib import *


# 核心是想明白如何把来数据包的ip与表项逐项比对寻找出最长前缀匹配，
# python内置有 IPv4Network IPv4Address对象
# 前者用于整合ip地址和mask，快速得出mask位数；后者用于与int()结合快速掩码ip，并进行ip比对
# 也可以直接用前者来标识子网
# 那么比对流程就是 摘取出IP包中的目的IP
# 循环每个 TableRow,逐个寻找符合最长前缀匹配的表项，若符合再比较掩码位数，
# 记住并更新最长前缀匹配表项index。不存在则为初始值-1
        

# 匹配到对应项后，IP header中TTL值-1，暂时不管过期
# 生成一个新的ethernet header，要根据next hop值来设置目标mac值。
# next hop的值不存在时需要生成arp query向其他人询问


class TableRow:
    def __init__(self,prefix,mask,nextHop,portName):
        self.subnet=IPv4Network(f'{prefix}/{mask}')

        self.prefix=IPv4Address(prefix)
        self.mask=IPv4Address(mask)
        self.nextHop=IPv4Address(nextHop)        
        self.portName=portName


class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        # other initialization stuff here
        self.portsList=net.interfaces()
        self.generateTable()

    def generateTable(self):
        table=[]
        with open('forwarding_table.txt', 'r') as fd:
            line = fd.readline()
            while line:
                rowList=line.split(' ')
                table.append(TableRow(rowList[0],rowList[1],rowList[2],rowList[3]))
                line = fd.readline()
        for port in self.net.portsList:
            table.append(TableRow(port.ipaddr,port.netmask,None,port.name))

        self.table=table

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):        
        timestamp, ifName, packet = recv
        # TODO: your logic here
        arpTable={}
        arp = packet.get_header(Arp)

        EthernetHeader=packet.get_header(Ethernet)
        IPv4Header=packet.get_header(IPv4)

        # search arp table if is arp query packet
        if arp:
            arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            # for key,val in arpTable.items():
            #     print(key,' arp pair ',val)
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

        # search forwarding table if not arp query
        elif IPv4Header:
            tarIndex=-1
            maxMask=0
            for index,row in enumerate(self.table):
                if IPv4Address(IPv4Header.src) in row.subnet and row.subnet.prefixlen>maxMask:
                    maxMask=row.subnet.prefixlen 
                    tarIndex=index
                    log_info(f'found target {index}')
                continue
            if tarIndex!=-1:
                IPv4Header.ttl-=1
                #if arp cache hit
                if (self.table[tarIndex].nextHop) in arpTable.keys():
                    EthernetHeader.dst=arpTable[self.table[tarIndex].nextHop]
                    newPacket=packet+IPv4Header+EthernetHeader
                    self.net.send_packet(self.table[tarIndex].portName,newPacket)
                #if not hit
                else:
                    #TODO generate arp query and push unfinished packet into queue

                    
                
        else:
            log_failure('no IP header found')



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
