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

# need some timer
swTimer=null


def try_send(net):
    global lhs,rhs,senderWindow
    if rhs-lhs+1<senderWindow:
        print('trying to send pkt')
    
def switchy_main(net,**kwargs):
    global lhs,rhs,senderWindow,num,blasteeIP
    my_intf = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_intf]
    myips = [intf.ipaddr for intf in my_intf]
    blasteeIP=IPv4Address(kwargs.blasteeIP)
    num=kwargs['num']
    length=kwargs['length']
    senderWindow=kwargs['senderWindow']
    timeout=kwargs['timeout']
    recvTimeout=kwargs['recvTimeout']

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
            pkt = Ethernet() + IPv4() + UDP()
            pkt[1].protocol = IPProtocol.UDP

            '''
            Do other things here and send packet
            '''

    net.shutdown()
