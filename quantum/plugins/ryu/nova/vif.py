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

from nova import flags
from nova import log as logging
from nova import utils
from nova.network.quantum import quantum_connection
from nova.virt.libvirt import vif as libvirt_vif


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


def _get_datapath_id(bridge_name):
    out, _err = utils.execute('ovs-vsctl', 'get', 'Bridge',
                              bridge_name, 'datapath_id', run_as_root=True)
    return out.strip().strip('"')


def _get_port_no(dev):
    out, _err = utils.execute('ovs-vsctl', 'get', 'Interface', dev,
                              'ofport', run_as_root=True)
    return int(out.strip())


class LibvirtOpenVswitchOFPRyuDriver(libvirt_vif.LibvirtOpenVswitchDriver):
    def __init__(self, **kwargs):
        super(LibvirtOpenVswitchOFPRyuDriver, self).__init__()
        LOG.debug('ryu rest host %s', FLAGS.libvirt_ovs_bridge)
        self.datapath_id = _get_datapath_id(FLAGS.libvirt_ovs_bridge)
        self.q_conn = quantum_connection.QuantumClientConnection()

    def _get_port_no(self, mapping):
        iface_id = mapping['vif_uuid']
        dev = self.get_dev_name(iface_id)
        return _get_port_no(dev)

    def _set_port_state(self, network, mapping, body):
        tenant_id = mapping['tenant_id']
        net_id = network['id']
        port_id = self.q_conn.get_port_by_attachment(tenant_id, net_id,
                                                     mapping['vif_uuid'])
        self.q_conn.client.set_port_state(net_id, port_id, body,
                                          tenant=tenant_id)

    def plug(self, instance, network, mapping):
        result = super(LibvirtOpenVswitchOFPRyuDriver, self).plug(
            instance, network, mapping)

        port_data = {
            'state': 'ACTIVE',
            'datapath_id': self.datapath_id,
            'port_no': self._get_port_no(mapping),
            'mac_address': mapping['mac'],
            }
        body = {'port': port_data}
        self._set_port_state(network, mapping, body)

        return result
