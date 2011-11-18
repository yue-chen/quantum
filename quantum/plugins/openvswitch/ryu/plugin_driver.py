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

import quantum.db.api as db
from quantum.common import exceptions as q_exc
from quantum.plugins.openvswitch import ovs_db
from quantum.plugins.openvswitch import ofp_service_type
from quantum.plugins.openvswitch.plugin_driver_base import PluginDriverBase
from ryu.app import client
from ryu.app import rest_nw_id


class OFPRyuDriver(PluginDriverBase):
    def __init__(self, config):
        OFP_CON_HOST = config.get("OVS", "openflow-controller")
        OFP_API_HOST = config.get("OVS", "openflow-rest-api")

        if OFP_CON_HOST is None or OFP_API_HOST is None:
            raise q_exc.Invalid("invalid configuration. "
                                "check ovs_quantum_plugin.ini")

        hosts = [(OFP_CON_HOST, ofp_service_type.CONTROLLER),
                 (OFP_API_HOST, ofp_service_type.REST_API)]
        ovs_db.add_ofp_servers(hosts)

        self.client = client.OFPClient(OFP_API_HOST)
        self.client.update_network(rest_nw_id.NW_ID_EXTERNAL)

        # register known all network list on startup
        self._create_all_tenant_network()

    def _create_all_tenant_network(self):
        networks = db.network_all_tenant_list()
        for net in networks:
            self.client.update_network(net.uuid)

    def create_network(self, net):
        self.client.create_network(net.uuid)

    def delete_network(self, net):
        self.client.delete_network(net.uuid)
