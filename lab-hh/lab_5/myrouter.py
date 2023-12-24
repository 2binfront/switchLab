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

        self.prefix=IPv4Address(prefix)
        self.mask=IPv4Address(mask)
        self.prefix=IPv4Address(int(self.prefix)&int(self.mask))
        self.subnet=IPv4Network(f'{self.prefix}/{mask}')
        if nextHop:
            self.nextHop=IPv4Address(nextHop) 
        else:
            self.nextHop=None
        self.portName=portName       
   
class UnfinishedPacket:
    def __init__(self,pkt,tableRow,tarIP:None) -> None:
        self.pkt=pkt
        if tarIP:
            self.tarIP=tarIP
        else:
            self.tarIP=tableRow.nextHop
        self.portName=tableRow.portName
        self.reCalls=0
        self.time=time.time()
        # self.time=0
        

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        # other initialization stuff here
        self.portsList=net.interfaces()
        self.queue=[]

    def sendArpPktRequest(self,operation,tarIP,ifname):
        log_info(f'port={ifname,len(ifname.rstrip())}\n')
        for port in self.portsList:
            if port.name==ifname.rstrip() or port.name==ifname:
                curport=port
                log_info(f'curport exist:{curport}')

        rePacket = Ethernet()
        rePacket.src =curport.ethaddr
        rePacket.dst = 'ff:ff:ff:ff:ff:ff'
        rePacket.ethertype = EtherType.ARP
        rePacket+=Arp(
            #reply type
            operation=operation,
            #router port ethaddr
            senderhwaddr=curport.ethaddr,
            #router port ip
            senderprotoaddr=curport.ipaddr,
            #original arp request hwaddr
            targethwaddr='ff:ff:ff:ff:ff:ff',
            #original arp request ipaddr
            targetprotoaddr= tarIP)
        log_info(f'curport exist again:{curport.name,rePacket}')

        self.net.send_packet(curport.name,rePacket)

    def sendArpPktReply(self,operation,senderIP,senderhwaddr,tarIP,tarhwaddr,ifname):
        rePacket = Ethernet()
        rePacket.src =senderhwaddr
        rePacket.dst = tarhwaddr
        rePacket.ethertype = EtherType.ARP
        rePacket+=Arp(
            #reply type
            operation=operation,
            #router port ethaddr
            senderhwaddr=senderhwaddr,
            #router port ip
            senderprotoaddr=senderIP,
            #original arp request hwaddr
            targethwaddr=tarhwaddr,
            #original arp request ipaddr
            targetprotoaddr= tarIP)
        self.net.send_packet(ifname.rstrip(),rePacket)

    def generateTable(self):
        table=[]
        # log_info(f'opening forwarding_table \n')

        with open('forwarding_table.txt', 'r') as fd:
            # log_info(f'opening forwarding_table {fd}\n')
            line = fd.readline()
            while line:
                rowList=line.split(' ')
                if not rowList[0]:
                    line = fd.readline()
                    continue
                table.append(TableRow(rowList[0],rowList[1],rowList[2],rowList[3]))
                line = fd.readline()


        for port in self.portsList:
            table.append(TableRow(port.ipaddr,port.netmask,None,port.name))
        self.table=table
        arpTable={}
        for port in self.portsList:
            arpTable[port.ipaddr]=port.ethaddr
        self.arpTable=arpTable

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):        
        timestamp, ifName, packet = recv
        log_info(f'got newpkt {packet} from {ifName}\n')
        # TODO: your logic here

        # search arp table if is arp query packet
        if packet.has_header(Arp):
            arp = packet.get_header(Arp)
            # log_info(f'got arp pkt {arp.operation}\n')
            self.arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            # for key,val in self.arpTable.items():
            #     print(key,' arp pair ',val)

            if arp.operation==ArpOperation.Request:
                if arp.targetprotoaddr in self.arpTable.keys():
                    self.sendArpPktReply(ArpOperation.Reply,arp.targetprotoaddr,self.arpTable[arp.targetprotoaddr],arp.senderprotoaddr,arp.senderhwaddr,ifName)
            elif arp.operation==ArpOperation.Reply:
                self.arpTable[arp.targetprotoaddr]=arp.targethwaddr

        # search forwarding table if not arp query
        elif packet.has_header(IPv4):
            IPv4Header=packet.get_header(IPv4)
            # log_info(f'got ip pkt {IPv4Header}\n')
            tarIndex=-1
            maxMask=0
            for index,row in enumerate(self.table):
                # log_info(f'finding {index} and {row.subnet}')
                if IPv4Address(IPv4Header.dst) in row.subnet and row.subnet.prefixlen>maxMask:
                    maxMask=row.subnet.prefixlen 
                    tarIndex=index
                    log_info(f'found target {IPv4Header.src} and {row.subnet}')
            log_info(f'targetIndex {tarIndex}')
            if tarIndex!=-1:
                # log_info(f'packet[IPv4].ttl={packet[IPv4].ttl}')
                log_info(f'IPv4Header={str(IPv4Header)}')
                packet[IPv4].ttl-=1
                # log_info(f'packet[IPv4].ttl={packet[IPv4].ttl}')

                if not self.table[tarIndex].nextHop:
                    log_info(f'rcsv detail:{ifName}\n')
                    nextIP=IPv4Header.dst
                else:
                    nextIP=self.table[tarIndex].nextHop


                #if arp cache hit
                if nextIP in self.arpTable.keys():
                    for port in self.portsList:
                        if port.name==self.table[tarIndex].portName:
                            curport=port

                    if not curport:
                        log_failure(f'curport not exist')

                    packet[Ethernet].src=curport.ethaddr
                    packet[Ethernet].dst=self.arpTable[nextIP]

                    log_info(f'sending packet={str(packet)}')
                    self.net.send_packet(self.table[tarIndex].portName,packet)
                #if not hit
                else:
                    log_info(f'rcsv port:{ifName}\n')
                    log_info(f'finding port:{self.table[tarIndex].portName}\n')
                    self.queue.append(UnfinishedPacket(packet,self.table[tarIndex],nextIP))
        else:
            log_failure('no valid header found')
        log_info('arptable as follows')
        for (k,v) in self.arpTable.items(): 
            print (f'{ k,v}') 
        log_info('table as follows')
        for item in self.table: 
            print (f'{item.subnet,item.nextHop,item.portName}') 

    def handle_queue(self):
        i=0
        
        while i< len(self.queue): 
        # single thread
        # if len(self.queue):
            item=self.queue[i]
            log_info(f'cur item={item.tarIP,item.time,time.time()}')
            if item.tarIP in self.arpTable.keys():
                for port in self.portsList:
                    log_info(f'{len(port.name),len(item.portName)}')
                    if port.name==item.portName or port.name==item.portName.rstrip():
                        curport=port

                item.pkt[Ethernet].src=curport.ethaddr
                item.pkt[Ethernet].dst=self.arpTable[item.tarIP]
                self.net.send_packet(curport.name,item.pkt)
                self.queue.pop(i)
                # return
                continue
                # i+=1
            if item.reCalls>=5:
                self.queue.pop(i)
                # continue
            else:
                curTime=time.time()
                if curTime - item.time>1 or item.reCalls==0:
                    log_info(f'shoulf send {item.reCalls}')
                    self.sendArpPktRequest(ArpOperation.Request,item.tarIP,item.portName)
                    item.reCalls+=1
                    item.time=time.time()
                    i+=1
            # log_info(f'i={i,len(self.queue)}')

            


    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        self.generateTable()
    
        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
                self.handle_packet(recv)
                self.handle_queue()
            except NoPackets:
                self.handle_queue()
                continue
            except Shutdown:
                break
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
