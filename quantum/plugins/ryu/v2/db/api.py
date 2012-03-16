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

import logging
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import exc

import quantum.db.api as db
from quantum.plugins.ryu.v2.db import models


LOG = logging.getLogger(__name__)


def set_ofp_servers(hosts):
    session = db.get_session()
    session.query(models.OFPServer).delete()
    for (host_address, host_type) in hosts:
        host = models.OFPServer(host_address, host_type)
        session.add(host)
    session.flush()


def ovs_node_update(dpid, tunnel_ip):
    session = db.get_session()
    dpid_or_ip = or_(models.OVSNode.dpid == dpid,
                     models.OVSNode.address == tunnel_ip)
    update = True
    try:
        nodes = session.query(models.OVSNode).filter(dpid_or_ip).all()
    except exc.NoResultFound:
        pass
    else:
        for node in nodes:
            if node.dpid == dpid and node.address == tunnel_ip:
                update = False
                continue
            if node.dpid == dpid:
                LOG.warn("updating node %s %s -> %s",
                         node.dpid, node.address, tunnel_ip)
            else:
                LOG.warn("deleting node %s", node)
            session.delete(node)

    if update:
        node = models.OVSNode(dpid, tunnel_ip)
        session.add(node)

    session.flush()


def ovs_node_all_list():
    session = db.get_session()
    return session.query(models.OVSNode).all()


_TUNNEL_KEY_MIN = 0
_TUNNEL_KEY_MAX = 0xffffffff


def _tunnel_key_last(session):
    try:
        last_key = session.query(models.TunnelKeyLast).one()
    except exc.MultipleResultsFound:
        max_key = session.query(func.max(models.TunnelKeyLast.last_key))
        if max_key > _TUNNEL_KEY_MAX:
            max_key = _TUNNEL_KEY_MIN

        session.query(models.TunnelKeyLast).all().delete()
        last_key = models.TunnelKeyLast(max_key)
        session.add(last_key)
    except exc.NoResultFound:
        last_key = models.TunnelKeyLast(_TUNNEL_KEY_MIN)
        session.add(last_key)

    return last_key


def _tunnel_key_allocate(session, last_key):
    """
    Try to find unused tunnel key in TunnelKey table starting
    from last_key + 1.
    When all keys are used, raise sqlalchemy.orm.exc.NoResultFound
    """
    # TODO: how to code the following without from_statement()?
    #       or is this better?
    #
    # key 0 = _TUNNLE_KEY_MIN is used for special meanings.
    # Don't allocate 0.
    new_key = session.query("new_key").from_statement(
        # If last_key + 1 isn't used, it's the result
        'SELECT new_key '
        'FROM (select :last_key + 1 AS new_key) q1 '
        'WHERE NOT EXISTS '
        '(SELECT 1 FROM tunnel_key WHERE tunnel_key = :last_key + 1) '

        'UNION ALL '

        # if last_key + 1 used, find the least unused key from last_key + 1
        '(SELECT t.tunnel_key + 1 AS new_key '
        'FROM tunnel_key t '
        'WHERE NOT EXISTS '
        '(SELECT 1 FROM tunnel_key ti WHERE ti.tunnel_key = t.tunnel_key + 1) '
        'AND t.tunnel_key >= :last_key '
        'ORDER BY new_key LIMIT 1) '

        'ORDER BY new_key LIMIT 1'
        ).params(last_key=last_key).one()
    new_key = new_key[0]  # the result is tuple.

    LOG.debug("last_key %s new_key %s", last_key, new_key)
    if new_key > _TUNNEL_KEY_MAX:
        LOG.debug("no key found")
        raise exc.NoResultFound
    return new_key


def tunnel_key_allocate(network_id):
    session = db.get_session()
    last_key = _tunnel_key_last(session)
    try:
        new_key = _tunnel_key_allocate(session, last_key.last_key)
    except exc.NoResultFound:
        new_key = _tunnel_key_allocate(session, _TUNNEL_KEY_MIN)

    tunnel_key = models.TunnelKey(network_id, new_key)
    last_key.last_key = new_key
    session.add(tunnel_key)
    session.flush()
    return new_key


def tunnel_key_delete(network_id):
    session = db.get_session()
    session.query(models.TunnelKey).filter_by(network_id=network_id).delete()
    session.flush()


def tunnel_key_all_list():
    session = db.get_session()
    return session.query(models.TunnelKey).all()
