#!/usr/bin/python
# name: topo-2sw-2host.py


from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, Host

class MyTopo( Topo ):
    "Simple topology example."

    def build( self,fo ):
        # Parámetro para el número de hosts por switch
        self.fo=fo

        # Nivel superior
        #top_switch = top_switch = self.addSwitch('Ts', cls=OVSKernelSwitch, dpid='0000000100002023')
        top_switch = self.addSwitch('Ts', cls=OVSKernelSwitch, dpid='0000000100002023')

        # Nivel de acceso
        for swNum in range(1, fo+1):
                Acceso = self.addSwitch('s{}'.format(swNum))
                self.addLink(top_switch, Acceso)
                # Nivel de hosts
                for hNum in range(1, 2*fo+1):
                        terminales = self.addHost('h_{}_{}'.format(swNum, hNum), cls=Host, ip='10.12.{}.{}/16'.format(swNum,hNum), defaultRoute=None)
                        self.addLink(terminales, Acceso)


topos = { 'mytopo': ( lambda fo=2: MyTopo(fo) ) }
