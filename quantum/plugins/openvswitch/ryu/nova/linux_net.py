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
from ryu.app.client import OFPClient

import ovs_utils

LOG = logging.getLogger('quantum.plugins.openvswitch.ryu.nova.linux_net')
FLAGS = flags.FLAGS
flags.DEFINE_string('linuxnet_ovs_ryu_api_host', '127.0.0.1:8080',
                    'Openflow Ryu REST API host:port')


#
# from nova.network import linux_net as nova_linux_net
# class LinuxOVSRyuInterfaceDriver(nova_linux_net.LinuxOVSInterfaceDriver):
# doesn't work
#
# nova.network.linux_net imports FLAGS.linuxnet_interface_driver
# We are being imported from linux_net so that we can't import linux_net
# to avoid circular import.
#
# Or factor out nova.network.linux_net somehow.
# load lazily FLAGS.linuxnet_interface_driver?
#

class LinuxOVSRyuInterfaceDriver(object):
    nova_linux_net = None

    def __init__(self):
        if self.nova_linux_net is None:
            self.nova_linux_net = utils.import_object('nova.network.linux_net')

        cls = utils.import_class(
            'nova.network.linux_net.LinuxOVSInterfaceDriver')
        self.parent = cls()

        LOG.debug('ryu rest host %s', FLAGS.linuxnet_ovs_ryu_api_host)
        self.ryu_client = OFPClient(FLAGS.linuxnet_ovs_ryu_api_host)
        self.datapath_id = ovs_utils.get_datapath_id(
            FLAGS.linuxnet_ovs_integration_bridge)

        if self.nova_linux_net.binary_name == 'nova-network':
            for tables in [self.nova_linux_net.iptables_manager.ipv4,
                           self.nova_linux_net.iptables_manager.ipv6]:
                tables['filter'].add_rule('FORWARD',
                        '--in-interface gw-+ --out-interface gw-+ -j DROP')
            self.nova_linux_net.iptables_manager.apply()

    def plug(self, network, mac_address, gateway=True):
        LOG.debug("network %s mac_adress %s gateway %s",
                  network, mac_address, gateway)
        ret = self.parent.plug(network, mac_address, gateway)
        port_no = ovs_utils.get_port_no(self.get_dev(network))
        self.ryu_client.create_port(network['uuid'], self.datapath_id, port_no)
        return ret

    def unplug(self, network):
        return self.parent.unplug(network)

    def get_dev(self, network):
        return self.parent.get_dev(network)
