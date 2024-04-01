#!/usr/bin/env python3

from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from random import randint
from time import time

#sender window >= rhs-lhs+1

lhs,rhs=1,1
senderWindow=0
num=0
blasteeIp=''
length=0
timeout=0

# need some timer and other tools
swTimestamp=0
latestAckedTimestamp=0
my_int=[]
mymacs=[]
myips=[]

#0-> not sent
#1-> sent but not acked
#2-> acked 
statusList=[]
retranPointer=-1

#Total TX time (in seconds): Time between the first packet sent and last packet ACKd
#Number of reTX: Number of retransmitted packets, this doesn't include the first transmission of a packet. Also if the same packet is retransmitted more than once, all of them will count
#Number of coarse TOs: Number of coarse timeouts
#Throughput (Bps): You will obtain this value by dividing the total # of sent bytes(from blaster to blastee) by total TX time. This will include all the retransmissions as well! When calculating the bytes, only consider the length of the variable length payload!
#Goodput (Bps): You will obtain this value by dividing the total # of sent bytes(from blaster to blastee) by total TX time. However, this will NOT include the bytes sent due to retransmissions! When calculating the bytes, only consider the length of the variable length payload!
total_tx_time=0
reTX_nums=0
to_times=0
throughput=0
goodput=0


def generatePkt(serialNo):
    global length,blasteeIp
    pkt = Ethernet() + IPv4() + UDP()
    pkt[1].protocol = IPProtocol.UDP
    pkt+=serialNo.to_bytes(4,byteorder='big',signed=False)
    pkt+=length.to_bytes(2,byteorder='big',signed=False)
    pkt+='this is payload part'.ljust(length, '.').encode()
    pkt[Ethernet].dst=EthAddr('40:00:00:00:00:01')
    pkt[IPv4].dst=IPv4Address(blasteeIp)
    pkt[Ethernet].src=EthAddr(mymacs[0])
    pkt[IPv4].src=IPv4Address(myips[0])
    return pkt


# try to send a packet regardless of whether received ack or not
## case 1: in retransmission
# case 2: sender window full, waiting ack, just continue
# case 3: not full, send 1 pkt immediately
def try_send(net):
    global lhs,rhs,senderWindow,statusList,timeout,swTimestamp,latestAckedTimestamp,my_intf
    global reTX_nums,to_times
    if swTimestamp==0:
        swTimestamp=time()
    if (swTimestamp-latestAckedTimestamp)*1000>timeout:
        print('trying to retransmit pkts')
        to_times+=1
        latestAckedTimestamp=time()
        retranPointer=lhs
        while retranPointer<=rhs:
            if statusList[retranPointer]==1:
                pkt=generatePkt(retranPointer)
                net.send_packet(my_intf[0],pkt)
                reTX_nums+=1
                retranPointer+=1
            else:
                retranPointer+=1
                continue
        print('retransmit pkts over')
    if rhs-lhs+1<senderWindow:
        print('senderWindow satisfied')
        if  statusList[rhs]==0:
            print('trying to send pkt')
            pkt=generatePkt(rhs)
            net.send_packet(my_intf[0],pkt)
            rhs+=1

    else:
        print('packet control mechanism has failed')
        print(f'lhs={lhs},rhs={rhs},sw={senderWindow}')
    
def switchy_main(net,**kwargs):
    """
    blasteeIp: IP address of the blastee. This value has to match the IP address value in the start_mininet.py file
    num: Number of packets to be sent by the blaster
    length: Length of the variable payload part of your packet in bytes, 0 ≤ length ≤ 65535
    senderWindow: Size of the sender window in packets
    timeout: Coarse timeout value in seconds
    recvTimeout: recv_packet timeout value in seconds. Blaster will block on recv_packet for at most recv_timeout. This will be a pseudo-rate controller for the blaster

    Args:
        net (_type_): _description_
    """
    start_time=time()
    global lhs,rhs,senderWindow,num,blasteeIp,length,timeout,mymacs,myips,my_intf,statusList,latestAckedTimestamp
    global total_tx_time,reTX_nums,to_times,throughput,goodput
    my_intf = net.interfaces()
    print(kwargs)
    mymacs = [intf.ethaddr for intf in my_intf]
    myips = [intf.ipaddr for intf in my_intf]
    blasteeIp=IPv4Address(kwargs['blasteeIp'])
    num=int(kwargs['num'])
    length=int(kwargs['length'])
    senderWindow=int(kwargs['senderWindow']) or 5
    timeout=int(kwargs['timeout'])
    recvTimeout=int(kwargs['recvTimeout']) or 0.15
    statusList=[0 for i in range(num+1)]
    try_send(net)
    while True:
        try:
            #Timeout value will be parameterized!
            # timestamp,dev,pkt = net.recv_packet(timeout=0.15)
            timestamp,dev,pkt = net.recv_packet(timeout=recvTimeout/1000)
        except NoPackets:
            log_debug("No packets available in recv_packet")
            try_send(net)
        except Shutdown:
            log_debug("Got shutdown signal")
            break
        else:
            payload=pkt[3]
            payload=payload.to_bytes()[:4]
            ackSerial=int.from_bytes(payload,byteorder='big',signed=False)
            statusList[ackSerial]=2
            latestAckedTimestamp=time()
            while statusList[lhs]==2:
                lhs+=1
            if lhs==num:
                break
            try_send(net)
    end_time=time()
    total_tx_time=end_time-start_time
    throughput=(reTX_nums+num)*length/total_tx_time
    goodput=(num)*length/total_tx_time

    print('Total TX time:',total_tx_time)
    print('Number of reTX:',reTX_nums)
    print('Number of coarse TOs:',to_times)
    print('Throughput (Bps):',throughput)
    print('Goodput (Bps):',goodput)


    net.shutdown()
