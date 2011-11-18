#!/usr/bin/env python
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

import ConfigParser
import logging as LOG
import sys
import time
import signal
import sqlalchemy

from optparse import OptionParser
from sqlalchemy.ext.sqlsoup import SqlSoup
from subprocess import *

OP_STATUS_UP = "UP"
OP_STATUS_DOWN = "DOWN"


# A class to represent a VIF (i.e., a port that has 'iface-id' and 'vif-mac'
# attributes set).
class VifPort:
    def __init__(self, port_name, ofport, vif_id, vif_mac, switch):
        self.port_name = port_name
        self.ofport = ofport
        self.vif_id = vif_id
        self.vif_mac = vif_mac
        self.switch = switch

    def __str__(self):
        return "iface-id=" + self.vif_id + ", vif_mac=" + \
          self.vif_mac + ", port_name=" + self.port_name + \
          ", ofport=" + self.ofport + ", bridge name = " + self.switch.br_name


class OVSBridge:
    def __init__(self, br_name):
        self.br_name = br_name

    def find_datapath_id(self):
        # ovs-vsctl get Bridge br-int datapath_id
        r = self.run_vsctl(["get", "Bridge", self.br_name, "datapath_id"])

        # remove preceding/trailing double quotes
        self.datapath_id = r.strip()[1:-1]

    def run_cmd(self, args):
        # LOG.debug("## running command: " + " ".join(args))
        p = Popen(args, stdout=PIPE)
        retval = p.communicate()[0]
        if p.returncode == -(signal.SIGALRM):
            LOG.debug("## timeout running command: " + " ".join(args))
        return retval

    def run_vsctl(self, args):
        full_args = ["ovs-vsctl", "--timeout=2"] + args
        return self.run_cmd(full_args)

    def reset_bridge(self):
        self.run_vsctl(["--", "--if-exists", "del-br", self.br_name])
        self.run_vsctl(["add-br", self.br_name])

    def set_controller(self, target):
        METHODS = ("ssl", "tcp", "unix", "pssl", "ptcp", "punix")
        x = target.split(":")
        if not x[0] in METHODS:
            target = "tcp:" + target
        self.run_vsctl(["set-controller", self.br_name, target])

    def delete_port(self, port_name):
        self.run_vsctl(["--", "--if-exists", "del-port", self.br_name,
          port_name])

    def set_db_attribute(self, table_name, record, column, value):
        args = ["set", table_name, record, "%s=%s" % (column, value)]
        self.run_vsctl(args)

    def clear_db_attribute(self, table_name, record, column):
        args = ["clear", table_name, record, column]
        self.run_vsctl(args)

    def run_ofctl(self, cmd, args):
        full_args = ["ovs-ofctl", cmd, self.br_name] + args
        return self.run_cmd(full_args)

    def remove_all_flows(self):
        self.run_ofctl("del-flows", [])

    def get_port_ofport(self, port_name):
        return self.db_get_val("Interface", port_name, "ofport")

    def add_flow(self, **dict):
        if "actions" not in dict:
            raise Exception("must specify one or more actions")
        if "priority" not in dict:
            dict["priority"] = "0"

        flow_str = "priority=%s" % dict["priority"]
        if "match" in dict:
            flow_str += "," + dict["match"]
        flow_str += ",actions=%s" % (dict["actions"])
        self.run_ofctl("add-flow", [flow_str])

    def delete_flows(self, **dict):
        all_args = []
        if "priority" in dict:
            all_args.append("priority=%s" % dict["priority"])
        if "match" in dict:
            all_args.append(dict["match"])
        if "actions" in dict:
            all_args.append("actions=%s" % (dict["actions"]))
        flow_str = ",".join(all_args)
        self.run_ofctl("del-flows", [flow_str])

    def db_get_map(self, table, record, column):
        str = self.run_vsctl(["get", table, record, column]).rstrip("\n\r")
        return self.db_str_to_map(str)

    def db_get_val(self, table, record, column):
        return self.run_vsctl(["get", table, record, column]).rstrip("\n\r")

    def db_str_to_map(self, full_str):
        list = full_str.strip("{}").split(", ")
        ret = {}
        for e in list:
            if e.find("=") == -1:
                continue
            arr = e.split("=")
            ret[arr[0]] = arr[1].strip("\"")
        return ret

    def get_port_name_list(self):
        res = self.run_vsctl(["list-ports", self.br_name])
        return res.split("\n")[0:-1]

    def get_port_stats(self, port_name):
        return self.db_get_map("Interface", port_name, "statistics")

    def get_xapi_iface_id(self, xs_vif_uuid):
        return self.run_cmd(
                        ["xe",
                        "vif-param-get",
                        "param-name=other-config",
                        "param-key=nicira-iface-id",
                        "uuid=%s" % xs_vif_uuid]).strip()

    def _vifport(self, name, external_ids):
        ofport = self.db_get_val("Interface", name, "ofport")
        return VifPort(name, ofport, external_ids["iface-id"],
                       external_ids["attached-mac"], self)

    def _get_ports(self, get_port):
        ports = []
        port_names = self.get_port_name_list()
        for name in port_names:
            port = get_port(name)
            if port is not None:
                ports.append(port)

        return ports

    # returns a VIF object for each VIF port
    def get_vif_ports(self):
        def _get_vif_port(name):
            external_ids = self.db_get_map("Interface", name, "external_ids")
            if "iface-id" in external_ids and "attached-mac" in external_ids:
                return self._vifport(name, external_ids)
            elif "xs-vif-uuid" in external_ids and \
                 "attached-mac" in external_ids:
                # if this is a xenserver and iface-id is not automatically
                # synced to OVS from XAPI, we grab it from XAPI directly
                ofport = self.db_get_val("Interface", name, "ofport")
                iface_id = self.get_xapi_iface_id(external_ids["xs-vif-uuid"])
                return VifPort(name, ofport, iface_id,
                               external_ids["attached-mac"], self)

            return None

        return self._get_ports(_get_vif_port)

    def get_external_ports(self):
        def _get_external_port(name):
            external_ids = self.db_get_map("Interface", name, "external_ids")
            if external_ids:
                return None

            ofport = self.db_get_val("Interface", name, "ofport")
            return VifPort(name, ofport, None, None, self)

        return self._get_ports(_get_external_port)

    @staticmethod
    def _is_managed_port(external_ids):
        return (external_ids and
                ("iface-id" in external_ids) and
                ("attached-mac" in external_ids) and
                ("iface-status" in external_ids))

    def get_gw_ports(self):
        def _get_gw_port(name):
            port_type = self.db_get_val("Interface", name, "type")
            if port_type != 'internal':
                return None

            external_ids = self.db_get_map("Interface", name, "external_ids")
            if not self._is_managed_port(external_ids):
                return None

            return self._vifport(name, external_ids)

        return self._get_ports(_get_gw_port)

    def get_vm_ports(self):
        def _get_vm_port(name):
            # status:driver_name = tun
            # type = ""
            port_type = self.db_get_val("Interface", name, "type")
            if port_type != '""':
                return None

            external_ids = self.db_get_map("Interface", name, "external_ids")
            if not self._is_managed_port(external_ids):
                return None

            status = self.db_get_val("Interface", name, "status")
            if 'driver_name=tun' not in status:
                return None

            return self._vifport(name, external_ids)

        return self._get_ports(_get_vm_port)


class OVSQuantumAgent:

    def __init__(self, config, integ_br, db):
        self.setup_integration_br(integ_br)

    def port_bound(self, port, vlan_id):
        self.int_br.set_db_attribute("Port", port.port_name, "tag",
                                                       str(vlan_id))
        self.int_br.delete_flows(match="in_port=%s" % port.ofport)

    def port_unbound(self, port, still_exists):
        if still_exists:
            self.int_br.clear_db_attribute("Port", port.port_name, "tag")

    def setup_integration_br(self, integ_br):
        self.int_br = OVSBridge(integ_br)
        self.int_br.remove_all_flows()
        # switch all traffic using L2 learning
        self.int_br.add_flow(priority=1, actions="normal")

    def daemon_loop(self, db):
        old_local_bindings = {}
        old_vif_ports = {}

        while True:

            all_bindings = {}
            try:
                ports = db.ports.all()
            except:
                ports = []
            for port in ports:
                all_bindings[port.interface_id] = port

            vlan_bindings = {}
            try:
                vlan_binds = db.vlan_bindings.all()
            except:
                vlan_binds = []
            for bind in vlan_binds:
                vlan_bindings[bind.network_id] = bind.vlan_id

            new_vif_ports = {}
            new_local_bindings = {}
            vif_ports = self.int_br.get_vif_ports()
            for p in vif_ports:
                new_vif_ports[p.vif_id] = p
                if p.vif_id in all_bindings:
                    net_id = all_bindings[p.vif_id].network_id
                    new_local_bindings[p.vif_id] = net_id
                else:
                    # no binding, put him on the 'dead vlan'
                    self.int_br.set_db_attribute("Port", p.port_name, "tag",
                              "4095")
                    self.int_br.add_flow(priority=2,
                           match="in_port=%s" % p.ofport, actions="drop")

                old_b = old_local_bindings.get(p.vif_id, None)
                new_b = new_local_bindings.get(p.vif_id, None)

                if old_b != new_b:
                    if old_b is not None:
                        LOG.info("Removing binding to net-id = %s for %s"
                          % (old_b, str(p)))
                        self.port_unbound(p, True)
                        if p.vif_id in all_bindings:
                            all_bindings[p.vif_id].op_status = OP_STATUS_DOWN
                    if new_b is not None:
                        # If we don't have a binding we have to stick it on
                        # the dead vlan
                        net_id = all_bindings[p.vif_id].network_id
                        vlan_id = vlan_bindings.get(net_id, "4095")
                        self.port_bound(p, vlan_id)
                        if p.vif_id in all_bindings:
                            all_bindings[p.vif_id].op_status = OP_STATUS_UP
                        LOG.info("Adding binding to net-id = %s " \
                             "for %s on vlan %s" % (new_b, str(p), vlan_id))

            for vif_id in old_vif_ports.keys():
                if vif_id not in new_vif_ports:
                    LOG.info("Port Disappeared: %s" % vif_id)
                    if vif_id in old_local_bindings:
                        old_b = old_local_bindings[vif_id]
                        self.port_unbound(old_vif_ports[vif_id], False)
                    if vif_id in all_bindings:
                        all_bindings[vif_id].op_status = OP_STATUS_DOWN

            old_vif_ports = new_vif_ports
            old_local_bindings = new_local_bindings
            db.commit()
            time.sleep(2)


def create_ofp_api_client(ofp_rest_api_addr):
    mod_str = "ryu.app.client"
    cls_str = "OFPClient"
    __import__(mod_str)
    cls = getattr(sys.modules[mod_str], cls_str)

    mod_str = "ryu.app.rest_nw_id"
    __import__(mod_str)
    nw_id = sys.modules[mod_str]

    return (cls(ofp_rest_api_addr), nw_id.NW_ID_EXTERNAL)


def check_ofp_mode(db):
    LOG.debug("checking db")

    try:
        servers = db.ofp_servers.all()
    except sqlalchemy.exc.NoSuchTableError:
        return None

    ofp_controller_addr = None
    ofp_rest_api_addr = None
    for s in servers:
        if s.host_type == "REST_API":
            ofp_rest_api_addr = s.address
        elif s.host_type == "controller":
            ofp_controller_addr = s.address

    LOG.debug("controller %s", ofp_controller_addr)
    LOG.debug("api %s", ofp_rest_api_addr)
    if ofp_controller_addr is None or ofp_rest_api_addr is None:
        return None

    LOG.debug("going to ofp controller mode %s %s",
              ofp_controller_addr, ofp_rest_api_addr)
    ofp_client, nw_id_external = create_ofp_api_client(ofp_rest_api_addr)
    return (ofp_client, ofp_controller_addr, nw_id_external)


class OVSQuantumOFPRyuAgent:
    def __init__(self, config, integ_br, db):
        ret = check_ofp_mode(db)
        assert ret

        ofp_api_client, ofp_controller_addr, nw_id_external = ret

        self.nw_id_external = nw_id_external
        self.api = ofp_api_client
        self._setup_integration_br(integ_br, ofp_controller_addr)

    def _setup_integration_br(self, integ_br, ofp_controller_addr):
        self.int_br = OVSBridge(integ_br)
        self.int_br.find_datapath_id()
        self.int_br.set_controller(ofp_controller_addr)
        for port in self.int_br.get_external_ports():
            self._port_update(self.nw_id_external, port)

    def _port_update(self, network_id, port):
        self.api.update_port(network_id, port.switch.datapath_id, port.ofport)

    def _all_bindings(self, db):
        """return interface id -> port which include network id bindings"""
        all_ports = db.ports.all()
        all_bindings = {}
        for port in all_ports:
            all_bindings[port.interface_id] = port

        return all_bindings

    def daemon_loop(self, db):
        # on startup, register all existing ports
        all_bindings = self._all_bindings(db)

        local_bindings = {}
        vif_ports = {}
        for p in self.int_br.get_vif_ports():
            vif_ports[p.vif_id] = p
            if p.vif_id in all_bindings:
                net_id = all_bindings[p.vif_id].network_id
                local_bindings[p.vif_id] = net_id
                self._port_update(net_id, p)
                all_bindings[p.vif_id].op_status = OP_STATUS_UP
                LOG.info("Updating binding to net-id = %s "
                         "for %s" % (net_id, str(p)))
        db.commit()

        old_vif_ports = vif_ports
        old_local_bindings = local_bindings

        while True:
            time.sleep(2)
            all_bindings = self._all_bindings(db)

            new_vif_ports = {}
            new_local_bindings = {}
            for p in self.int_br.get_vif_ports():
                new_vif_ports[p.vif_id] = p
                if p.vif_id in all_bindings:
                    net_id = all_bindings[p.vif_id].network_id
                    new_local_bindings[p.vif_id] = net_id

                old_b = old_local_bindings.get(p.vif_id, None)
                new_b = new_local_bindings.get(p.vif_id, None)

                if old_b != new_b:
                    if old_b is not None:
                        LOG.info("Removing binding to net-id = %s for %s"
                          % (old_b, str(p)))
                        if p.vif_id in all_bindings:
                            all_bindings[p.vif_id].op_status = OP_STATUS_DOWN
                    if new_b is not None:
                        if p.vif_id in all_bindings:
                            all_bindings[p.vif_id].op_status = OP_STATUS_UP
                        LOG.info("Adding binding to net-id = %s " \
                                 "for %s" % (new_b, str(p)))

            for vif_id in old_vif_ports.keys():
                if vif_id not in new_vif_ports:
                    LOG.info("Port Disappeared: %s" % vif_id)
                    if vif_id in all_bindings:
                        all_bindings[vif_id].op_status = OP_STATUS_DOWN

            old_vif_ports = new_vif_ports
            old_local_bindings = new_local_bindings
            db.commit()


def create_plugin(config, integ_br, db):
    agent_driver = config.get("OVS", "agent_driver")
    LOG.info("agent_driver = %s", agent_driver)
    cls = getattr(sys.modules[__name__], agent_driver)
    return cls(config, integ_br, db)


CONFIG_DEFAULT = {"agent_driver": "OVSQuantumAgent"}


if __name__ == "__main__":
    usagestr = "%prog [OPTIONS] <config file>"
    parser = OptionParser(usage=usagestr)
    parser.add_option("-v", "--verbose", dest="verbose",
      action="store_true", default=False, help="turn on verbose logging")

    options, args = parser.parse_args()

    if options.verbose:
        LOG.basicConfig(level=LOG.DEBUG)
    else:
        LOG.basicConfig(level=LOG.WARN)

    if len(args) != 1:
        parser.print_help()
        sys.exit(1)

    config_file = args[0]
    config = ConfigParser.ConfigParser(CONFIG_DEFAULT)
    try:
        config.read(config_file)
    except Exception, e:
        LOG.error("Unable to parse config file \"%s\": %s" % (config_file,
          str(e)))

    integ_br = config.get("OVS", "integration-bridge")

    options = {"sql_connection": config.get("DATABASE", "sql_connection")}
    db = SqlSoup(options["sql_connection"])

    LOG.info("Connecting to database \"%s\" on %s" %
             (db.engine.url.database, db.engine.url.host))
    plugin = create_plugin(config, integ_br, db)
    plugin.daemon_loop(db)

    sys.exit(0)
