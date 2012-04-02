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
from nova.network import linux_net
from nova.network.quantum import quantum_connection


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


class LinuxOVSRyuInterfaceDriver(linux_net.LinuxOVSInterfaceDriver):
    def __init__(self):
        super(LinuxOVSRyuInterfaceDriver, self).__init__()
        self.q_conn = quantum_connection.QuantumClientConnection()

        self.datapath_id = _get_datapath_id(
            FLAGS.linuxnet_ovs_integration_bridge)

        if linux_net.binary_name == 'nova-network':
            for tables in [linux_net.iptables_manager.ipv4,
                           linux_net.iptables_manager.ipv6]:
                tables['filter'].add_rule('FORWARD',
                        '--in-interface gw-+ --out-interface gw-+ -j DROP')
            linux_net.iptables_manager.apply()

    def _set_port_state(self, network, dev, body):
        tenant_id = network['tenant_id']
        net_id = network['uuid']
        port_id = self.q_conn.get_port_by_attachment(tenant_id, net_id, dev)
        self.q_conn.client.set_port_state(net_id, port_id,
                                          body, tenant=tenant_id)

    def plug(self, network, mac_address, gateway=True):
        LOG.debug("network %s mac_adress %s gateway %s",
                  network, mac_address, gateway)
        ret = super(LinuxOVSRyuInterfaceDriver, self).plug(
            network, mac_address, gateway)

        dev = self.get_dev(network)
        port_data = {
            'state': 'ACTIVE',
            'datapath_id': self.datapath_id,
            'port_no': _get_port_no(dev),
            'mac_address': mac_address,
            }
        body = {'port': port_data}
        self._set_port_state(network, dev, body)

        return ret
