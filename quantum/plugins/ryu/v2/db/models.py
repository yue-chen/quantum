# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2012 Isaku Yamahata <yamahata at private email ne jp>
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from quantum.db.models import BASE
from quantum.db.models import QuantumBase
from quantum.db import models


class OFPServer(BASE, QuantumBase):
    """Openflow Server/API address"""
    __tablename__ = 'ofp_server'

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(255))       # netloc <host ip address>:<port>
    host_type = Column(String(255))     # server type
                                        # Controller, REST_API

    def __init__(self, address, host_type):
        super(OFPServer, self).__init__()
        self.address = address
        self.host_type = host_type

    def __repr__(self):
        return "<OFPServer(%s,%s,%s)>" % (self.id, self.address,
                                          self.host_type)


class OVSNode(BASE, QuantumBase):
    """IP Addresses used for tunneling"""
    __tablename__ = 'ovs_node'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dpid = Column(String(255))          # datapath id
    address = Column(String(255))       # ip address used for tunneling

    def __init__(self, dpid, address):
        super(OVSNode, self).__init__()
        self.dpid = dpid
        self.address = address

    def __repr__(self):
        return "<OVSNode(%s,%s,%s)>" % (self.id, self.dpid, self.address)


class TunnelKeyLast(BASE, QuantumBase):
    __tablename__ = 'tunnel_key_last'

    last_key = Column(Integer, primary_key=True)

    def __init__(self, last_key):
        super(TunnelKeyLast, self).__init__()
        self.last_key = last_key

    def __repr__(self):
        return "<TunnelKeyLast(%x)>" % self.last_key


class TunnelKey(BASE, QuantumBase):
    """Netowrk ID <-> GRE tunnel key mapping"""
    __tablename__ = 'tunnel_key'

    # Network.uuid
    network_id = Column(String(255), primary_key=True, nullable=False)
    tunnel_key = Column(Integer, unique=True, nullable=False)

    def __init__(self, network_id, tunnel_key):
        super(TunnelKey, self).__init__()
        self.network_id = network_id
        self.tunnel_key = tunnel_key

    def __repr__(self):
        return "<TunnelKey(%s,%x)>" % (self.network_id, self.tunnel_key)
