'''

'''

from copy import copy
from itertools import chain, izip
from pybigip import core


class VirtualAddress(object):
    '''
    '''
    _ip = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con, name):
        ''' '''
        self._con = con
        self._lcon = con.LocalLB.VirtualAddressV2
        self.name = name

    @property
    def ip(self):
        '''
        '''
        if self._ip is None:
            self._ip = self._lcon.get_address([self.name])[0]

        return self._ip


class VirtualServer(object):
    '''
    '''
    _pool = None
    _address = None
    _destination = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con, name):
        '''
        '''
        self._con = con
        self._lcon = self._con.LocalLB.VirtualServer
        self.name = name

    @property
    def destination(self):
        '''
        '''
        if self._destination is None:
            self._destination = self._lcon.get_destination_v2([self.name])[0]

        return self._destination


    @property
    def address(self):
        '''
        '''
        if not self._address:
            self._address = VirtualAddress(self._con, self.destination['address'])

        return self._address

    @property
    def port(self):
        '''
        '''
        return self.destination['port']

    @property
    def pool(self):
        '''
        '''
        if not self._pool:
            name = self._lcon.get_default_pool_name([self.name])[0]
            self._pool = Pool(self._con, name)

        return self._pool

    @pool.setter
    def pool(self, new):
        '''
        '''
        self._pool = new
        self._lcon.set_default_pool_name([self.name], [new.name])

@core.memoize
class VirtualServers(core.ObjectList):
    '''
    Class for managing the VIPs on the bigip.
    '''
    klass = VirtualServer

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    @property
    def _lcon(self):
        return self._con.LocalLB.VirtualServer

    def to_list(self):
        return [v.to_dict() for v in self._objects]


@core.memoize
class Pools(object):
    '''
    Class for managing the pools on the bigip.
    '''
    _names = None
    _all = False

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con):
        '''
        Setup pool.

        @param con: bigsuds connection object
        '''
        self._con = con
        self._lcon = self._con.LocalLB.Pool
        self._pools = dict()

    def add(self, pool):
        '''
        Add a new pool.

        @param pool:
        '''
        self.add_multi([pool])

    def add_multi(self, pools):
        '''
        Add a list of pools.

        @param pools:
        '''
        names = list()
        methods = list()
        members = list()

        for pool in pools:
            names.append(pool.name)
            methods.append(pool.method)
            members.append([m.to_dict() for m in pool.members])

        self._con.create_v2(names, methods, members)

    def remove(self, pool):
        '''
        '''
        self.remove_multi([pool])

    def remove_multi(self, pools):
        '''
        '''
        self._lcon.delete_pool([p.name for p in pools])

    def get(self, name, nocache=False, deep=False):
        '''
        Lookup pool by name.

        @param name: Pool name
        @return: Pool object
        '''
        return self.get_multi([name,], nocache, deep)

    def get_all(self, nocache=False, deep=False):
        '''
        Get list of all pools.

        @return: List of Pool objects
        '''
        return self.get_multi(self.names, nocache, deep)

    def get_multi(self, names, nocache=False, deep=False):
        '''
        Get a set of pools

        @param names:
        @keyword deep:
        @keyword nocache:
        @return: List of Pool objects
        '''
        missing = list()
        pools = list()

        if nocache:
            missing = names
        else:
            for name in names:
                try:
                    pools.append(self._pools[name])
                except KeyError:
                    missing.append(name)

        if missing:
            temp = self.load(missing, deep)
            pools += temp
            self._pools.update(dict(((p.name, p) for p in temp)))

        return pools

    def load(self, names, deep=False):
        '''
        Read pool from bigip.

        @param names: Pool names
        @return: list of Pool object
        '''
        print "calling get_member_v2(%s...[%d])" % (repr(names)[:70], len(repr(names)))
        members = self._lcon.get_member_v2(names)
        ret = list()

        for name, members in izip(names, members):
            pool = Pool(self._con, name)
            pool._members = [Member(self._con, pool=pool, **m) for m in members]
            ret.append(pool)

        if deep:
            self.load_all_member_ips(ret)
            self.load_all_member_status(ret)

        return ret

    @property
    def names(self): 
        '''
        Lazy load names of pools on the bigip.

        @return list of pool names.
        '''
        if not self._names:
            self._names = self._lcon.get_list()

        return self._names

    def load_all_member_ips(self, pools):
        '''
        Load member ip information for all members of this pool in one
        call to the LTM.
        '''
        load = list()
        names = list()

        for i, pool in enumerate(pools):
            temp = list() 

            for j, member in enumerate(pool.members):
                if not member._ip:
                    temp.append({'member': member.to_dict(),
                                 'pindex': i,
                                 'mindex': j})

            if temp:
                names.append(pool.name)
                load.append(temp)

        if not load:
            return

        addresses = [[x['member'] for x in y] for y in load]
        print "calling get_member_address(%s...)" % repr(addresses)[:70]
        ips = self._lcon.get_member_address(names, addresses)

        for i, members in enumerate(ips):
            for j, ip in enumerate(members):
                member = load[i][j]
                pools[member['pindex']].members[member['mindex']]._ip = ip

    def load_all_member_status(self, pools=None):
        '''
        Load memer status information for all members of the pools specified in
        `pools`
        '''
        load = list()
        names = list()

        if pools is None:
            pools = self._pools.values()

        for i, pool in enumerate(pools):
            temp = list()

            for j, member in enumerate(pool.members):
                if not member._status:
                    add = {'member': member.to_dict(),
                                 'pindex': i,
                                 'mindex': j}
                    temp.append(add)

            if temp:
                names.append(pool.name)
                load.append(temp)

        members = [[x['member'] for x in y] for y in load]
        statuses = self._lcon.get_member_object_status(names, members)

        for i, members in enumerate(statuses):
            for j, status in enumerate(members):
                member = load[i][j]
                pools[member['pindex']].members[member['mindex']]._status = status

    def all_ips(self): 
        '''
        Get list of every ip assigned as a pool member.

        @return: list of ip addresses
        '''
        self.load_all_member_ips()
        ip_gen = (x.ips() for x in self.pools.itervalues())
        return list(set(chain.from_iterable(ip_gen)))


class Pool(object):
    '''
    Pool representation
    '''
    _members = None
    _vips = None
    _status = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con, name, members=None, method=None):
        '''
        @param con: bigsuds connection object
        @param name: name of this pool
        @keyword members: list of members
        @keyword method: load balancing method
        '''
        self._con = con
        self._lcon = self._con.LocalLB.Pool
        self.name = name
        self._members = members
        self._method = method

    @property
    def members(self):
        '''
        Lazy load list of pool members.

        @return list of pool member dicts.
        '''
        if not self._members:
            members = self._lcon.get_member_v2([self.name])[0]
            self._members = [Member(self._con, pool=self, **m) for m in members]

        return self._members

    @property
    def method(self):
        '''
        Lazy load pool load balancing method.

        @return: 
        '''
        if not self._method:
            self._method = self._lcon.get_lb_method([self.name])[0]

        return self._method

    def add_member(self, member):
        '''
        '''
        self.add_member_multi(self, [member])

    def add_member_multi(self, members):
        '''
        '''
        members = [m.to_dict() for m in self.members]
        self._con.add_member_v2([self.name], members)

    def remove_member(self, member):
        '''
        '''
        self.remove_member_multi(self, [member])

    def remove_member_multi(self, members):
        '''
        '''
        member_dicts = [m.to_dict() for m in members]
        self._lcon.remove_member_v2([self.name], member_dicts)

    def statistics(self):
        '''
        Get member statistics for this pool.
        
        @return bigip statistics dict.
        '''
        return self._lcon.get_statistics([self.name])

    def ips(self):
        '''
        Get list of ip addresses for this pools members.

        @return list of ip addresses
        '''
        return [member.ip for member in self.members]

    def status(self, nocache=False):
        '''
        Get pool status

        @return:
        '''
        if nocache or not self._status:
            print "calling get_object_status(%r)" % self.name
            self._status = self._lcon.get_object_status([self.name])[0]

        return self._status

    @property
    def enabled(self):
        '''
        Get enabled state for this pool.
        '''
        return self.status()['enabled_status'] == 'ENABLED_STATUS_ENABLED'

    @property
    def available(self):
        '''
        Get availability state for this pool.

        @return: bool
        '''
        return self.status()['availability_status'] == 'AVAILABILITY_STATUS_GREEN'

    def load_all_member_status(self, nocache=False):
        '''
        Load member status information for all members of this pool in one
        call to the LTM.
        '''
        load = list()

        for i, member in enumerate(self.members):
            if nocache or not member._status:
                load.append({'member': member.to_dict(),
                             'index': i})

        stats = self._lcon.get_member_object_status([self.name,],
            [[x['member'] for x in load]])

        for i, status in enumerate(stats[0]):
            self.members[load[i]['index']]._status = status

    def load_all_member_ips(self, nocache=False):
        '''
        Load member ip information for all members of this pool in one
        call to the LTM.
        '''
        self.pool.load_all_member_ips([self.name,], nocache)

    @property
    def virtual_servers(self):
        if self._vips is None:
            self._vips = list()
            all_vips = VirtualServers(self._con).get_all()
            for vip in all_vips:
                if vip.pool.name == self.name:
                    self._vips.append(vip)

        return self._vips


class Member(object):
    '''
    Pool member representation
    '''
    _status = None
    _ip = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con, address, port, pool=None):
        ''' '''
        self._con = con
        self._lcon = self._con.LocalLB.Pool
        self.address = address
        self.port = port
        self.pool = pool

    def to_dict(self):
        '''
        Get dict representation of the member to be used when interacting with
        the iControl API.

        return:
        '''
        return {'address': self.address, 'port': self.port}

    def metadata(self):
        '''
        '''
        return self._lcon.get_member_metadata([self.pool.name],
                                              [[self.to_dict()]])[0][0]

    def status(self, nocache=False):
        '''
        '''
        if not self._status or nocache:
            self._status = self._lcon.get_member_object_status(
                    [self.pool.name], [[self.to_dict()]])[0][0]

        return self._status

    @property
    def ip(self):
        '''
        '''
        if not self._ip:
            self._ip = self._lcon.get_member_address(
                    [self.pool.name], [[self.to_dict()]])[0][0]
        return self._ip

    @property
    def priority(self):
        '''

        '''
        return self._lcon.get_member_priority([self.pool.name],
                                              [[self.to_dict()]])[0][0]

    @priority.setter
    def priority(self, value):
        '''
        '''
        self._lcon.set_member_priority([self.pool.name],
                                       [[self.to_dict()]],
                                       [[value]])

    @property
    def enabled(self):
        '''
        Get enabled state for this pool.
        '''
        return self.status()['enabled_status'] == 'ENABLED_STATUS_ENABLED'

    @property
    def available(self):
        '''
        Get availability state for this pool.

        @return: bool
        '''
        return self.status()['availability_status'] == 'AVAILABILITY_STATUS_GREEN'


class Nodes(object):
    '''
    Node address representation
    '''
    _names = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con):
        ''' '''
        self._con = con
        self._nodes = dict()

    @property
    def _lcon(self):
        return self._con.LocalLB.NodeAddressV2

    @property
    def names(self):
        ''' '''
        if not self._names:
            self._names = self._lcon.get_list()

        return self._names

    def get(self, name, nocache=False):
        ''' '''
        return self.get_multi([name,], nocache)

    def get_all(self, nocache=False):
        ''' '''
        return self.get_multi(self.names, nocache)

    def get_multi(self, names, nocache=False):
        ''' '''
        missing = list()
        nodes = list()

        if nocache:
            missing = names
        else:
            for name in names:
                try:
                    nodes.append(self._nodes[name])
                except KeyError:
                    missing.append(name)

        if missing:
            temp = self.load(missing)
            nodes += temp
            self._nodes = dict(((n.name, n) for n in temp))

        return nodes

    def load(self, names):
        '''
        '''
        nodes = self._lcon.get_address(names)
        return [Node(self._con, n, a) for n, a in izip(names, nodes)]


class Node(object):
    '''
    '''
    _pools = None

    def __getstate__(self):
        state = copy(self.__dict__)
        state['_con'] = None
        state['_lcon'] = None
        return state

    def __init__(self, con, name, address):
        '''
        '''
        self._con = con
        self.name = name
        self.address = address

    @property
    def pools(self):
        if self._pools is None:
            self._pools = list()
            all_pools = Pools(self._con).get_all(deep=True)

            for pool in all_pools:
                if self.address in pool.ips():
                    self._pools.append(pool)

        return self._pools
