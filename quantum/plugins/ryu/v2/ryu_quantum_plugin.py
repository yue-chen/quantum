# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2012 Isaku Yamahata <yamahata at private email ne jp>
#                               <yamahata at valinux co jp>
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
# @author: Isaku Yamahata

from sqlalchemy.orm import exc as sql_exc

import quantum.db.api as db
from quantum.common import exceptions as q_exc
from quantum.common.config import find_config_file
from quantum.plugins.ryu import ofp_service_type
from quantum.plugins.ryu import ovs_quantum_plugin_base
from quantum.plugins.ryu.v2.db import api as ryu_db

from ryu.app import client
from ryu.app import rest_nw_id
from ryu.app.client import ignore_http_not_found


CONF_FILE = find_config_file({"plugin": "ryu"}, None, "ryu_v2.ini")


class OFPRyuDriver(ovs_quantum_plugin_base.OVSQuantumPluginDriverBase):
    def __init__(self, config):
        super(OFPRyuDriver, self).__init__()
        ofp_con_host = config.get("OVS", "openflow-controller")
        ofp_api_host = config.get("OVS", "openflow-rest-api")

        if ofp_con_host is None or ofp_api_host is None:
            raise q_exc.Invalid("invalid configuration. check ryu.ini")

        hosts = [(ofp_con_host, ofp_service_type.CONTROLLER),
                 (ofp_api_host, ofp_service_type.REST_API)]
        ryu_db.set_ofp_servers(hosts)

        self.client = client.OFPClient(ofp_api_host)
        self.gt_client = client.GRETunnelClient(ofp_api_host)
        self.client.update_network(rest_nw_id.NW_ID_EXTERNAL)
        self.client.update_network(rest_nw_id.NW_ID_VPORT_GRE)

        # register known all network list on startup
        self._create_all_tenant_network()

    def _create_all_tenant_network(self):
        for net in db.network_all_tenant_list():
            self.client.update_network(net.uuid)
        for tun in ryu_db.tunnel_key_all_list():
            self.gt_client.update_tunnel_key(tun.network_id,
                                             tun.tunnel_key)

    def create_network(self, net):
        tunnel_key = ryu_db.tunnel_key_allocate(net.uuid)
        self.client.create_network(net.uuid)
        self.gt_client.create_tunnel_key(net.uuid, tunnel_key)

    def delete_network(self, net):
        ignore_http_not_found(lambda: self.client.delete_network(net.uuid))
        ignore_http_not_found(lambda:
                              self.gt_client.delete_tunnel_key(net.uuid))

        try:
            ryu_db.tunnel_key_delete(net.uuid)
        except sql_exc.NoResultFound:
            raise q_exc.NetworkNotFound(net_id=net.uuid)


class RyuQuantumPlugin(ovs_quantum_plugin_base.OVSQuantumPluginBase):
    def __init__(self, configfile=None):
        super(RyuQuantumPlugin, self).__init__(CONF_FILE, __file__, configfile)
        self.driver = OFPRyuDriver(self.config)
