'''

'''


from itertools import chain, izip
from pybigip import core

class VirtualAddress(object):
    '''
    '''
    _ip = None

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


class VirtualServers(core.ObjectList):
    '''
    Class for managing the VIPs on the bigip.
    '''
    klass = VirtualServer

    def __init__(self, con):
        ''' '''
        super(VirtualServers, self).__init__(con)
        self._lcon = con.LocalLB.VirtualServer


class Pools(object):
    '''
    Class for managing the pools on the bigip.
    '''
    _names = None
    _all = False

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

    def get(self, name, reload=False):
        '''
        Lookup pool by name.

        @param name: Pool name
        @return: Pool object
        '''
        self.get_multi([name], reload)

    def get_all(self, reload=False):
        '''
        Get list of all pools.

        @return: List of Pool objects
        '''
        return self.get_multi(self.names, reload)

    def get_multi(self, names, reload=False):
        '''
        Get a set of pools

        @param names:
        @keyword reload:
        @return: List of Pool objects
        '''
        missing = list()
        pools = list()

        if reload:
            missing = names
        else:
            for name in names:
                try:
                    pools.append(self.pools[name])
                except KeyError:
                    missing.append(name)
        
        if missing:
            temp = self.load(missing)
            pools += temp
            self._pools = dict(((p.name, p) for p in temp))

        return pools

    def load(self, names):
        '''
        Read pool from bigip.

        @param names: Pool names
        @return: list of Pool object
        '''
        pools = self._con.get_member_v2(names)
        return [Pool(self._con, n, p) for n, p in izip(names, pools)]

    @property
    def names(self):
        '''
        Lazy load names of pools on the bigip.

        @return list of pool names.
        '''
        if not self._names:
            self._names = self._lcon.get_list()

        return self._names

    def all_ips(self):
        '''
        Get list of every ip assigned as a pool member.

        @return: list of ip addresses
        '''
        ip_gen = (x.ips() for x in self.pools.itervalues())
        return list(set(chain.from_iterable(ip_gen)))


class Pool(object):
    '''
    Pool representation
    '''
    _members = None
    _status = None

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
        return [member.address for member in self.members]

    def status(self, reload=False):
        '''
        Get pool status

        @return:
        '''
        if reload or not self._status:
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

    def load_all_member_status(self, reload=False):
        '''
        Load member status information for all members of this pool in one
        call to the LTM.
        '''
        load = list()

        for i, member in enumerate(self.members):
            if reload or not member._status:
                load.append({'member': member.to_dict(),
                             'index': i})

        stats = self._lcon.get_member_object_status([self.name,],
            [[x['member'] for x in load]])

        for i, status in enumerate(stats[0]):
            self.members[load[i]['index']]._status = status


class Member(object):
    '''
    Pool member representation
    '''
    _status = None

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

    def status(self, reload=False):
        '''
        '''
        if not self._status or reload:
            self._status = self._lcon.get_member_object_status(
                    [self.pool.name], [[self.to_dict()]])[0][0]

        return self._status

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
