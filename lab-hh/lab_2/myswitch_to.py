'''
Ethernet learning switch in Python.

Note that this file currently has the code to implement a "hub"
in it, not a learning switch.  (I.e., it's currently a switch
that doesn't learn.)
'''
import switchyard
from switchyard.lib.userlib import *


def main(net: switchyard.llnetbase.LLNetBase):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]

    #list of (srcMac,srcPort,timestamp)
    switchTable=[]

    while True:
        try:
            timestamp, fromIface, packet = net.recv_packet()
        except NoPackets:
            continue
        except Shutdown:
            break
        else:
            log_info(f"incomePort:{fromIface} incomeMac:{packet.get_header(Ethernet).src}")
            switchTable.append((packet.get_header(Ethernet).src,fromIface,timestamp))
        log_debug (f"In {net.name} received packet {packet} on {fromIface}")
        eth = packet.get_header(Ethernet)
        if eth is None:
            log_info("Received a non-Ethernet packet?!")
            return
        if eth.dst in mymacs:
            log_info("Received a packet intended for me")
        else:
            #find the intf in switchTable
            if switchTable.get(eth.dst,False):
                log_info(f"getResult:{switchTable.get(eth.dst,False)} sending packet {packet} to {switchTable[eth.dst]}")
                net.send_packet(switchTable[eth.dst], packet)
            else:
                for intf in my_interfaces:
                    if fromIface!= intf.name:
                        log_info (f"Flooding packet {packet} to {intf.name}")
                        net.send_packet(intf, packet)

    net.shutdown()
