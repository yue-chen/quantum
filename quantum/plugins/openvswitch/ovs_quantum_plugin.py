# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 Nicira Networks, Inc.
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
# @author: Somik Behera, Nicira Networks, Inc.
# @author: Brad Hall, Nicira Networks, Inc.
# @author: Dan Wendlandt, Nicira Networks, Inc.

import logging as LOG

from quantum.common.config import find_config_file
from quantum.plugins.ovscommon import ovs_quantum_plugin_base

import ovs_db

CONF_FILE = find_config_file(
  {"config_file": "etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini"},
  None, "ovs_quantum_plugin.ini")

LOG.basicConfig(level=LOG.WARN)
LOG.getLogger("ovs_quantum_plugin")


class VlanMap(object):
    vlans = {}
    net_ids = {}
    free_vlans = set()

    def __init__(self):
        self.vlans.clear()
        self.net_ids.clear()
        self.free_vlans = set(xrange(2, 4094))

    def set_vlan(self, vlan_id, network_id):
        self.vlans[vlan_id] = network_id
        self.net_ids[network_id] = vlan_id

    def acquire(self, network_id):
        if len(self.free_vlans):
            vlan = self.free_vlans.pop()
            self.set_vlan(vlan, network_id)
            # LOG.debug("VlanMap::acquire %s -> %s", vlan, network_id)
            return vlan
        else:
            raise Exception("No free vlans..")

    def get(self, vlan_id):
        return self.vlans.get(vlan_id, None)

    def release(self, network_id):
        vlan = self.net_ids.get(network_id, None)
        if vlan is not None:
            self.free_vlans.add(vlan)
            del self.vlans[vlan]
            del self.net_ids[network_id]
            # LOG.debug("VlanMap::release %s", vlan)
        else:
            LOG.error("No vlan found with network \"%s\"", network_id)


class OVSQuantumPluginDriver(
    ovs_quantum_plugin_base.OVSQuantumPluginDriverBase):
    def __init__(self):
        self.vlanmap = VlanMap()

        # Populate the map with anything that is already present in the
        # database
        vlans = ovs_db.get_vlans()
        for x in vlans:
            vlan_id, network_id = x
            # LOG.debug("Adding already populated vlan %s -> %s"
            #                                   % (vlan_id, network_id))
            self.vlanmap.set_vlan(vlan_id, network_id)

    def create_network(self, net):
        network_id = str(net.uuid)
        vlan = self.vlanmap.acquire(network_id)
        ovs_db.add_vlan_binding(vlan, network_id)

    def delete_network(self, net):
        network_id = net.uuid
        ovs_db.remove_vlan_binding(network_id)
        self.vlanmap.release(network_id)


class OVSQuantumPlugin(ovs_quantum_plugin_base.OVSQuantumPluginBase):
    def __init__(self, configfile=None):
        super(OVSQuantumPlugin, self).__init__(CONF_FILE, __file__, configfile)
        self.driver = OVSQuantumPluginDriver()
