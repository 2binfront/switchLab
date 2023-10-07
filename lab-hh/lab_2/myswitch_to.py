'''
Ethernet learning switch in Python.

Note that this file currently has the code to implement a "hub"
in it, not a learning switch.  (I.e., it's currently a switch
that doesn't learn.)
'''
import switchyard
from switchyard.lib.userlib import *
import time

def main(net: switchyard.llnetbase.LLNetBase):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]

    #mac:(interface,timestamp)
    #if check timestamp when new packet'srcMac already exist in the table:
    #   if same srcport:
    #       reuse
    #   else:
    #       update
    #else:
    #   append new key-value map
    #
    #also check every item's curtime-timestamp>10s?del:nothing
    switchTable={}

    while True:
        try:
            timestamp, fromIface, packet = net.recv_packet()
        except NoPackets:
            continue
        except Shutdown:
            break
        else:
            t = time.time()
            switchTable[packet.get_header(Ethernet).src]=(fromIface,t)
            for mac in list(switchTable.keys()):
                if t-switchTable[mac][1]>=5:
                    del switchTable[mac]
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
                net.send_packet(switchTable[eth.dst][0], packet)
            else:
                for intf in my_interfaces:
                    if fromIface!= intf.name:
                        log_info (f"Flooding packet {packet} to {intf.name}")
                        net.send_packet(intf.name, packet)

    net.shutdown()
