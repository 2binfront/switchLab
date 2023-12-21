#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
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
   
class UnfinishedPacket:
    def __init__(self,pkt,tableRow) -> None:
        self.pkt=pkt
        self.tableRow=tableRow
        self.reCalls=1
        self.time=time.time()
        

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        # other initialization stuff here
        self.portsList=net.interfaces()
        self.generateTable()
        self.queue=[]

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

        arpTable={}
        for port in self.portsList:
            arpTable[port.ipaddr]=port.ethaddr
        self.arpTable=arpTable




    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):        
        timestamp, ifName, packet = recv
        # TODO: your logic here
        arp = packet.get_header(Arp)

        EthernetHeader=packet.get_header(Ethernet)
        IPv4Header=packet.get_header(IPv4)

        # search arp table if is arp query packet
        if arp:
            self.arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            # for key,val in self.arpTable.items():
            #     print(key,' arp pair ',val)

            if arp.operation==ArpOperation.Request:
                if self.arpTable[arp.targetprotoaddr]:
                    rePacket = Ethernet()
                    rePacket.src =self.arpTable[arp.targetprotoaddr]
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
                    self.net.send_packet(ifName,rePacket)
            elif arp.operation==ArpOperation.Reply:
                self.arpTable[arp.targetprotoaddr]=arp.targethwaddr

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
                if self.table[tarIndex].nextHop==None:
                    return
                IPv4Header.ttl-=1
                #if arp cache hit
                if (self.table[tarIndex].nextHop) in self.arpTable.keys():
                    EthernetHeader.dst=self.arpTable[self.table[tarIndex].nextHop]
                    newPacket=packet+IPv4Header+EthernetHeader
                    self.net.send_packet(self.table[tarIndex].portName,newPacket)
                #if not hit
                else:
                    #TODO generate arp query and put unfinished packet into queue
                    arpEth=Ethernet()
                    arpEth.src=self.arpTable[self.table[tarIndex].prefix] 
                    arpEth.dst='ff:ff:ff:ff:ff:ff'
                    arpEth.ethertype=EtherType.ARP
                    arpPkt=arpEth+Arp(
                        operation=ArpOperation.Request,
                        senderprotoaddr=self.table[tarIndex].prefix,
                        senderhwaddr=self.arpTable[self.table[tarIndex].prefix] ,
                        targetprotoaddr=self.table[tarIndex].nextHop,
                        targethwaddr='ff:ff:ff:ff:ff:ff'
                    )
                    self.net.send_packet(self.table[tarIndex].portName,arpPkt)

                    self.queue.append(UnfinishedPacket(packet,self.table[tarIndex]))

                    
                
        else:
            log_failure('no IP header found')

    def handle_queue(self):
        i=0
        while i< len(self.queue):
            item=self.queue[i]
            if item.reCalls>5:
                self.queue.pop(i)
                continue
            else:
                if time.time()- item.time>1:
                    arpEth=Ethernet()
                    arpEth.src=self.arpTable[item.prefix] 
                    arpEth.dst='ff:ff:ff:ff:ff:ff'
                    arpEth.ethertype=EtherType.ARP
                    arpPkt=arpEth+Arp(
                        operation=ArpOperation.Request,
                        senderprotoaddr=item.prefix,
                        senderhwaddr=self.arpTable[item.prefix] ,
                        targetprotoaddr=item.nextHop,
                        targethwaddr='ff:ff:ff:ff:ff:ff'
                    )
                    self.net.send_packet(item.portName,arpPkt)
                    item.reCalls+=1
                    item.time=time.time()
                    i+=1
            


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
            #todo handle the queue
            self.handle_queue()

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
