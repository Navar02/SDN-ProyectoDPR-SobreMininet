from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types



class TreeControl13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TreeControl13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        # Accion para el tratamiento del evento SwitchFeatures, que ocurre en el momento de establecer
        # una conexion entre el controlador RYU y un switch nuevo.
        # Como estamos usando OpenFlow v1.3, lo primero que hacemos es instalar un flujo
        # "catch all" de prioridad minima, que indique al switch que envie al controlador todos los
        # paquetes

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        CONTROLLER_PORT = ofproto.OFPP_CONTROLLER

        # Regla catch-all de prioridad 0
        match = parser.OFPMatch() # match vacio: empareja con todo
        actions = [parser.OFPActionOutput(CONTROLLER_PORT, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        # Solicitud de descripcion de los puertos del switch
        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

    def add_flow_ip(self, datapath, priority, ip_src, ip_dst, out_port, buffer_id=None):
        # Especializacion de add_flow que instala flujos indicando la direccion IP/mascara de origen
        # (o None), la dirección IP/mascara de destino (o None) y el puerto de salida
        # Notese que si ambas direcciones son None la regla instalada empareja con el tráfico IP, pero
        # no con traficos no-IP como puede ser ARP. Notese tambien que es necesario especificar 
        # una prioridad

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(out_port)]

        if (ip_src == None and ip_dst == None):
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP)
        elif ip_src == None:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=ip_dst)
        elif ip_dst == None:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=ip_src)
        else:
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, ipv4_src=ip_src, ipv4_dst = ip_dst)

        self.add_flow(datapath, priority, match, actions)
        self.logger.info("Installed a flow in %s from %s to %s via %s", datapath.id, ip_src, ip_dst, out_port)


    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        # Funcion para insertar flujos genericos en un switch. Requiere especificar una prioridad, 
        # un match y unas acciones. Prepara y envia un paquete FlowMod

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        # Accion por omision para PacketIn: inundar pero sin instalar ningun flujo
        # Con un control totalmente proactivo, no debería ejecutarse nunca

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.logger.info("Packet in switch %s source %s dest. %s output %s", dpid, src, dst, in_port)

        out_port = ofproto.OFPP_ALL
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)



    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        # Accion de recogida de datos con descripciones de los puertos de un switch, obtenida
        # como respuesta a un envío de mensaje OFPPortDescStatsRequest
        # La respuesta tiene tantas secciones como puertos. Se incluye un puerto especial de control,
        # no usado para datos normales

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        ALL_PORT = ofproto.OFPP_ALL
        parser = datapath.ofproto_parser
        dpid = datapath.id

        num_ports = 0
        for p in ev.msg.body:
            num_ports += 1
           
        self.logger.info("\t Total number of ports of switch %s including control: %d" % 
                         (dpid, num_ports))

        num_ports = num_ports - 1 # Puertos fisicos -- quitamos el de control

        #Determinar si es el switch Ts o los de acceso
        if dpid < 65:
            #Obtener número de hosts y de switches
            nhosts = num_ports -1
            print(nhosts)
            ip_org='10.12.{}.0/24'.format(dpid)
            print(ip_org)
            self.add_flow_ip(datapath, 1, ip_org ,'10.12.0.0/16', 1)
            #Direcciones src
            for h in range(1, nhosts + 1):
                ip_org = '10.12.{}.{}/16'.format(dpid, h)
                ip_dest = '10.12.{}.{}/32'.format(dpid, h)
                self.add_flow_ip(datapath, 2, ip_org, ip_dest, h+1)

        else:
            #Switch superior
            print("Switch sup " + str(dpid))
            #Direcciones src
            for s in range(1, num_ports + 1):
                ip_org = '10.12.0.0/16'.format(s)
                ip_dest = '10.12.{}.0/24'.format(s)
                self.add_flow_ip(datapath, 1, ip_org, ip_dest, s)

