#!/usr/bin/env python3

from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from random import randint
import time

#sender window >= rhs-lhs+1

lhs,rhs=1,1
senderWindow=0
num=0
blasteeIP=''
length=0
timeout=0
# need some timer
swTimer=0

#0-> not sent
#1-> sent but not acked
#2-> acked 
statusList=[]

retranState=False
retranPinter=-1
retranTimes=0
retranPktsNo=0

# try to send a packet regardless of whether received ack or not
# case 1: in retransmission
# case 2: sender window full, waiting ack
# case 3: not full, send 1 pkt immediately
def try_send(net):
    global lhs,rhs,senderWindow,statusList
    if rhs-lhs+1<=senderWindow:
        if not statusList[rhs]:
            print('trying to send pkt')
            newpkt = Ethernet() + IPv4() + UDP()
            newpkt[1].protocol =IPProtocol.UDP
    else:
        print('packet control mechanism has failed')
    
def switchy_main(net,**kwargs):
    """

    blasteeIP: IP address of the blastee. This value has to match the IP address value in the start_mininet.py file
    num: Number of packets to be sent by the blaster
    length: Length of the variable payload part of your packet in bytes, 0 ≤ length ≤ 65535
    senderWindow: Size of the sender window in packets
    timeout: Coarse timeout value in seconds
    recvTimeout: recv_packet timeout value in seconds. Blaster will block on recv_packet for at most recv_timeout. This will be a pseudo-rate controller for the blaster

    Args:
        net (_type_): _description_
    """
    global lhs,rhs,senderWindow,num,blasteeIP,length,timeout
    my_intf = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_intf]
    myips = [intf.ipaddr for intf in my_intf]
    blasteeIP=IPv4Address(kwargs.blasteeIP)
    num=int(kwargs['num'])
    length=int(kwargs['length'])
    senderWindow=int(kwargs['senderWindow']) or 5
    timeout=int(kwargs['timeout'])
    recvTimeout=int(kwargs['recvTimeout']) or 0.15

    try_send(net)
    while True:
        gotpkt = True
        try:
            #Timeout value will be parameterized!
            # timestamp,dev,pkt = net.recv_packet(timeout=0.15)
            timestamp,dev,pkt = net.recv_packet(timeout=recvTimeout)
        except NoPackets:
            log_debug("No packets available in recv_packet")
            try_send(net)
            gotpkt = False
        except Shutdown:
            log_debug("Got shutdown signal")
            break
        else:

            if gotpkt:
                log_debug("I got a packet")
            else:
                log_debug("Didn't receive anything")

            '''
            Creating the headers for the packet
            '''
            newpkt = Ethernet() + IPv4() + UDP()
            newpkt[1].protocol = IPProtocol.UDP

            '''
            Do other things here and send packet
            '''

    net.shutdown()
