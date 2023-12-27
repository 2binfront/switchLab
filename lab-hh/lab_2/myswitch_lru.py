'''
Ethernet learning switch in Python.

Note that this file currently has the code to implement a "hub"
in it, not a learning switch.  (I.e., it's currently a switch
that doesn't learn.)
'''
import switchyard
from switchyard.lib.userlib import *

size=5


def main(net: switchyard.llnetbase.LLNetBase):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]

    switchTable={}

    while True:
        try:
            _, fromIface, packet = net.recv_packet()
        except NoPackets:
            continue
        except Shutdown:
            break
        else:
            log_info(f"incomePort:{fromIface} incomeMac:{packet[Ethernet].src}")
            if switchTable.get(packet[Ethernet].src):
                switchTable[packet[Ethernet].src][0]=fromIface
            else:
                if len(switchTable)==size:
                    tmp=sorted(switchTable.items(),key=(lambda x:x[1][1]),reverse=True)
                    del switchTable[tmp[0][0]]
                switchTable[packet[Ethernet].src]=[fromIface,0]
            for key in switchTable.keys():
                # if key!=packet[Ethernet].src:
                    switchTable[key][1]+=1

            log_info(f"In {net.name} received packet {packet} on {fromIface}")
            eth = packet[Ethernet]
            if eth is None:
                log_info("Received a non-Ethernet packet?!")
                return
            if eth.dst in mymacs:
                log_info("Received a packet intended for me")
            else:
                #find the intf in switchTable
                if switchTable.get(eth.dst,False):
                    log_info(f"getResult:{switchTable.get(eth.dst,False)} sending packet {packet} to {switchTable[eth.dst]}")
                    switchTable[eth.dst][1]=0
                    net.send_packet(switchTable[eth.dst][0], packet)
                else:
                    for intf in my_interfaces:
                        if fromIface!= intf.name:
                            log_info (f"Flooding packet {packet} to {intf.name}")
                            net.send_packet(intf.name, packet)
                print(switchTable)
            

    net.shutdown()
