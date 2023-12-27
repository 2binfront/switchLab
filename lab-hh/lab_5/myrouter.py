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

# 涉及生成icmp包之后，应当把某个逻辑抽离出来
# 这个逻辑是：根据dst ip，查forwarding_table，找到能转发出去的端口，然后确定next_hop_ip，再查arp_table，
# 能找到下一跳ip对应的mac就直接设置好dst mac，src mac，src ip发出去，找不到，就和对应的转发表项、next_hop_ip包装，
# 放进未完成队列，每个周期检查一次arp_table，没有就发一次arp request，recall times>5就滚蛋
# 单纯转发包基本类似，唯一不同是坚决不能动 ip header内容，不能改src ip，如何区分？？？

# 在哪里有这些逻辑的身影？（data内容另说
# 1.收到ICMPEchoRequest,且其目的ip为路由器某端口时，dst ip为request包的src ip
# 2.收到不会引起错误的非arp包，单纯转发该包，调用以上逻辑，icmpFlag=0
# 3.找不到转发表项，生成icmp error包，递归调用以上逻辑
# 4.queue中遇到recall times>5，需要生成icmp error包，调用以上逻辑
# 5.收到非icmp包，但目的ip是路由器的某一端口，需要生成icmp error包，调用以上逻辑
# 6.找到对应表项，但递减ip ttl时降至0，需要生成icmp error包，递归调用以上逻辑
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
    def __init__(self,pkt,port,tarIP,icmpFlag) -> None:
        self.pkt=pkt
        self.tarIP=tarIP
        self.port=port
        self.icmpFlag=icmpFlag
        self.reCalls=0
        self.time=time.time()
        self.arpSent=0
        

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        # other initialization stuff here
        self.portsList=net.interfaces()
        self.ipList=[]
        self.macList=[]
        for port in self.portsList:
            self.ipList.append(port.ipaddr)
            self.macList.append(port.ethaddr)
        self.queue=[]

    def generateTable(self):
        table=[]
        with open('forwarding_table.txt', 'r') as fd:
            line = fd.readline()
            while line:
                line=line.strip('\n')
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
        # for port in self.portsList:
        #     arpTable[port.ipaddr]=port.ethaddr
        self.arpTable=arpTable

    def sendArpPktRequest(self,tarIP,ifname):
        log_info(f'port={ifname,len(ifname)}\n')
        for port in self.portsList:
            if port.name==ifname:
                curport=port
                log_info(f'curport exist:{curport}')

        rePacket = Ethernet()
        rePacket.src =curport.ethaddr
        rePacket.dst = 'ff:ff:ff:ff:ff:ff'
        rePacket.ethertype = EtherType.ARP
        rePacket+=Arp(
            #reply type
            operation=ArpOperation.Request,
            #router port ethaddr
            senderhwaddr=curport.ethaddr,
            #router port ip
            senderprotoaddr=curport.ipaddr,
            #original arp request hwaddr
            targethwaddr='ff:ff:ff:ff:ff:ff',
            #original arp request ipaddr
            targetprotoaddr= tarIP)
        log_info(f'curport exist again:{curport.name,str(rePacket)}')
        self.net.send_packet(curport,rePacket)

    def sendArpPktReply(self,senderIP,senderhwaddr,tarIP,tarhwaddr,ifname):
        for port in self.portsList:
            if port.name==ifname:
                curport=port
        log_info(f'coming arpReply packet={curport}')
        rePacket = Ethernet()
        rePacket.src =senderhwaddr
        rePacket.dst = tarhwaddr
        rePacket.ethertype = EtherType.ARP
        rePacket+=Arp(
            #reply type
            operation=ArpOperation.Reply,
            #router port ethaddr
            senderhwaddr=senderhwaddr,
            #router port ip
            senderprotoaddr=senderIP,
            #original arp request hwaddr
            targethwaddr=tarhwaddr,
            #original arp request ipaddr
            targetprotoaddr= tarIP)
        log_info(f'sending arpReply packet={str(rePacket)}')
        self.net.send_packet(curport,rePacket)

    def generateICMPReply(self,packet):
        i = ICMP()
        i.icmptype=ICMPType.EchoReply
        i.icmpdata.data=packet[ICMP].icmpdata.data
        i.icmpdata.identifier=packet[ICMP].icmpdata.identifier
        i.icmpdata.sequence=packet[ICMP].icmpdata.sequence
        i.icmpcode=ICMPTypeCodeMap[ICMPType.EchoReply]
        #default upper protocol: ICMP
        ipHeader=IPv4()
        ipHeader.dst=packet[IPv4].src
        ipHeader.src=packet[IPv4].dst
        ipHeader.ttl=64
        etHeader=Ethernet()
        log_info(f'icmp reply looks like:{ipHeader+i}')
        # etHeader.src=self.macList[self.ipList.index(packet[IPv4].dst)]
        # etHeader.dst=packet[Ethernet].src
        return etHeader+ipHeader+i   
    
    def generateICMPError(self,packet,errorType,errorCode):
        ipHeader=IPv4()
        #default upper protocol: ICMP
        ipHeader.protocol = IPProtocol.ICMP
        ipHeader.dst=packet[IPv4].src
        ipHeader.src=packet[IPv4].dst
        ipHeader.ttl=64

        etHeader=Ethernet()
        # etHeader.src=packet[Ethernet].dst
        # etHeader.dst=packet[Ethernet].src

        i = ICMP()
        i.icmptype=errorType
        del packet[Ethernet]
        i.icmpdata.data=packet.to_bytes()[:28]
        if errorType==ICMPType.TimeExceeded:
            i.icmpdata.origdgramlen = len(packet)
        else:
            i.icmpcode=errorCode

        return etHeader+ipHeader+i        

    def get_target_ip(self,IPv4Header,targetIndex):
        if not self.table[targetIndex].nextHop:
            return IPv4Header.dst
        else:
            return self.table[targetIndex].nextHop

    def lookup_foward_table(self,IPv4Header):
        tarIndex=-1
        maxMask=0
        for index,row in enumerate(self.table):
            # log_info(f'finding {index} and {row.subnet}')
            if IPv4Address(IPv4Header.dst) in row.subnet and row.subnet.prefixlen>maxMask:
                maxMask=row.subnet.prefixlen 
                tarIndex=index
                log_info(f'found target {IPv4Header.src} and {row.subnet}')
        return tarIndex
    
    def forward_packet(self,packet,icmpFlag):
        tarIndex=self.lookup_foward_table(packet[IPv4])
        if tarIndex==-1:
            packet=self.generateICMPError(packet,ICMPType.DestinationUnreachable,ICMPTypeCodeMap[ICMPType.DestinationUnreachable].NetworkUnreachable)
            self.forward_packet(packet,1)
        else:
            if packet[IPv4].ttl<=1:
                log_info(f'in forward_packet ttl expired')
                packet=self.generateICMPError(packet,ICMPType.TimeExceeded,None)
                self.forward_packet(packet,1)
            else:
                log_info(f'in forward_packet ttl={packet[IPv4].ttl-1}')
                packet[IPv4].ttl-=1
                nextIP=self.get_target_ip(packet[IPv4],tarIndex)
                for port in self.portsList:
                    if port.name==self.table[tarIndex].portName:
                        curPort=port
                if nextIP in self.arpTable:
                    if icmpFlag:
                        packet[IPv4].src=curPort.ipaddr
                    packet[Ethernet].dst=self.arpTable[nextIP]
                    packet[Ethernet].src=curPort.ethaddr
                    self.net.send_packet(curPort,packet)
                else:
                    self.queue.append(UnfinishedPacket(packet,curPort,nextIP,icmpFlag))

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):        
        timestamp, ifName, packet = recv
        log_info(f'got newpkt {packet} from {ifName}\n')
        for port in self.portsList:
            if port.name==ifName:
                curInterface=port

        # search arp table if is arp query packet
        if packet.has_header(Arp):
            arp = packet.get_header(Arp)
            if packet[Ethernet].dst!='ff:ff:ff:ff:ff:ff' and packet[Ethernet].dst!=curInterface.ethaddr:
                log_info(f'got malicious arp pkt {packet}, dropping\n')
                return

            log_info(f'got arp pkt {str(arp)}\n')
            # log_info(f'got arp pkt {arp.targetprotoaddr}\n')
            # log_info(f'got arp pkt {str(self.ipList)}\n')
            self.arpTable[arp.senderprotoaddr]=arp.senderhwaddr
            # for key,val in self.arpTable.items():
            #     print(key,' arp pair ',val)
            if arp.operation==ArpOperation.Request:
                if arp.targetprotoaddr in self.ipList:
                    self.sendArpPktReply(arp.targetprotoaddr,self.macList[self.ipList.index(arp.targetprotoaddr)],arp.senderprotoaddr,arp.senderhwaddr,ifName)
            elif arp.operation==ArpOperation.Reply:
                self.arpTable[arp.targetprotoaddr]=arp.targethwaddr

        # search forwarding table if not arp query
        elif packet.has_header(IPv4):
            if packet.has_header(ICMP) and packet[IPv4].dst in self.ipList and packet[ICMP].icmptype==ICMPType.EchoRequest:        
                log_info(f'got ICMP echo request pkt {str(packet),ifName}\n')
                packet=self.generateICMPReply(packet)
                self.forward_packet(packet,0)
            elif packet[IPv4].dst in self.ipList and not packet.has_header(ICMP):
                log_info(f'got pkt dst in router but not icmp {str(packet)}\n')
                packet=self.generateICMPError(packet,ICMPType.DestinationUnreachable,ICMPTypeCodeMap[ICMPType.DestinationUnreachable].PortUnreachable)
                self.forward_packet(packet,1)
            else:
                log_info(f'got normal pkt {str(packet)}\n')
                self.forward_packet(packet,0)

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
        # for _item in self.queue:
        #     _item.arpSent=0
        while i< len(self.queue): 
        # single thread
        # if len(self.queue):
            item=self.queue[i]
            # log_info(f'cur item={item.tarIP,str(item.pkt),item.time,time.time()}')
            if item.tarIP in self.arpTable.keys():
                if item.icmpFlag:
                    item.pkt[IPv4].src=item.port.ipaddr
                item.pkt[Ethernet].src=item.port.ethaddr
                item.pkt[Ethernet].dst=self.arpTable[item.tarIP]
                self.net.send_packet(item.port,item.pkt)
                self.queue.pop(i)
                continue
            if item.reCalls>=5:
                packet=self.generateICMPError(item.pkt,ICMPType.DestinationUnreachable,ICMPTypeCodeMap[ICMPType.DestinationUnreachable].HostUnreachable)
                self.forward_packet(packet,1)
                self.queue.pop(i)
            else:
                curTime=time.time()
                if (curTime - item.time>1 or item.reCalls==0) and not item.arpSent:
                    log_info(f'sending arpRequest: {item.reCalls}times')
                    self.sendArpPktRequest(item.tarIP,item.port.name)
                    item.reCalls+=1
                    item.time=curTime
                    i+=1
                    for j in range(i,len(self.queue)):
                        self.queue[j].arpSent=1
                        self.queue[j].reCalls+=1
                        self.queue[j].time=curTime
                item.arpSent=0


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
