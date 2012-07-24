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

import sqlalchemy as sa

from quantum.db import model_base


class OFPServer(model_base.BASEV2):
    """Openflow Server/API address."""
    __tablename__ = 'ofp_server'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    address = sa.Column(sa.String(64))        # netloc <host ip address>:<port>
    host_type = sa.Column(sa.String(255))     # server type
                                              # Controller, REST_API

    def __repr__(self):
        return "<OFPServer(%s,%s,%s)>" % (self.id, self.address,
                                          self.host_type)


class TunnelKeyLast(model_base.BASEV2):
    """Lastly allocated Tunnel key. The next key allocation will be started
    from this value + 1
    """
    last_key = sa.Column(sa.Integer, primary_key=True)

    def __repr__(self):
        return "<TunnelKeyLast(%x)>" % self.last_key


class TunnelKey(model_base.BASEV2):
    """Netowrk ID <-> tunnel key mapping."""
    network_id = sa.Column(sa.String(36), sa.ForeignKey("networks.id"),
                           nullable=False)
    tunnel_key = sa.Column(sa.Integer, primary_key=True,
                           nullable=False, autoincrement=False)

    def __repr__(self):
        return "<TunnelKey(%s,%x)>" % (self.network_id, self.tunnel_key)


class OVSNode(model_base.BASEV2):
    """IP Addresses used for tunneling."""
    __tablename__ = 'ovs_node'

    dpid = sa.Column(sa.String(255), primary_key=True)  # datapath id
    address = sa.Column(sa.String(255))       # ip address used for tunneling

    def __init__(self, dpid, address):
        self.dpid = dpid
        self.address = address

    def __repr__(self):
        return "<OVSNode(%s,%s)>" % (self.dpid, self.address)


class PortBinding(model_base.BASEV2):
    """Represents Port binding to ovs ports."""
    __tablename__ = 'port_binding'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    network_id = sa.Column(sa.String(255), sa.ForeignKey("networks.id"),
                           nullable=False)
    port_id = sa.Column(sa.String(255), sa.ForeignKey("ports.id"), unique=True,
                        nullable=False)
    dpid = sa.Column(sa.String(255), sa.ForeignKey("ovs_node.dpid"),
                     nullable=False)
    port_no = sa.Column(sa.Integer, nullable=False)
    mac_address = sa.Column(sa.String(255), nullable=False)

    def __init__(self, network_id, port_id, dpid, port_no, mac_address):
        self.network_id = network_id
        self.port_id = port_id
        self.dpid = dpid
        self.port_no = port_no
        self.mac_address = mac_address

    def __repr__(self):
        return "<PortBinding(%s,%s,%s,%s,%s)>" % (self.network_id,
                                                  self.port_id,
                                                  self.dpid,
                                                  self.port_no,
                                                  self.mac_address)


class SequenceBase(model_base.QuantumBaseV2):
    """Sequence Number for detecting changes to TunnelPortBase."""
    sequence = sa.Column(sa.Integer, primary_key=True)

    def __repr__(self):
        return "<%s(%d)>" % (self.__class__.__name__, self.sequence)


class TunnelPortBase(model_base.QuantumBaseV2):
    """Tunnel Port."""
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    src_dpid = sa.Column(sa.String(255), nullable=False)
    dst_dpid = sa.Column(sa.String(255), nullable=False)

    def __init__(self, src_dpid, dst_dpid):
        self.src_dpid = src_dpid
        self.dst_dpid = dst_dpid

    def __repr__(self):
        return "<%s(%s,%s)>" % (self.__class__.__name__,
                                self.src_dpid,
                                self.dst_dpid)


class TunnelPortRequestSequence(model_base.BASEV2, SequenceBase):
    __tablename__ = "tunnel_port_request_sequence"

    def __init__(self, sequence):
        self.sequence = sequence


class TunnelPortRequest(model_base.BASEV2, TunnelPortBase):
    """Tunnel Port that should be created."""
    __tablename__ = "tunnel_port_request"


class TunnelPortSequence(model_base.BASEV2, SequenceBase):
    __tablename__ = "tunnel_port_sequence"

    def __init__(self, sequence):
        self.sequence = sequence


class TunnelPort(model_base.BASEV2, TunnelPortBase):
    """Tunnel Port that exists."""
    __tablename__ = "tunnel_port"
