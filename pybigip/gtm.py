'''
GTM Interfaces.

Example (Disable datacenter for a distributed application):
    >>> con = pybigip.Connection('gtm.example.company', 'admin', 'foobarbaz')
    >>> myapp = pybigip.gtm.Application(con, '/Common/myapp')
    >>> myapp.datacenters['/Common/SFO'].enabled = False
'''

import itertools
from pybigip import core


class Applications(core.ObjectList):
    '''
    Access Distributed Applications.
    '''
    def __init__(self, con):
        '''
        '''
        super(Applications, self).__init__(con)
        self._lcon = self._con.GlobalLB.Application

    def load(self, names):
        '''
        Override parent load method to preload Application datacenter status
        data.
        '''
        ret = list()
        app_dcs = self._lcon.get_data_centers(names)
        app_desc = self._lcon.get_description(names)

        for app, dcs, desc in itertools.izip(names, app_dcs, app_desc):
            app_obj = Application(self._con, app)
            app_obj._dcs = dict(((dc, Datacenter(app_obj, dc)) for dc in dcs))
            app_obj._description = desc
            ret.append(app_obj)

        return ret


class Application(object):
    '''
    A Distributed Application.
    '''
    _description = None
    _wips = None

    def __init__(self, con, name, dcs=None):
        '''
        '''
        self._con = con
        self._lcon = self._con.GlobalLB.Application
        self.name = name
        self._dcs = dcs

    def get_ctx(self, name, type):
        '''
        Get application object context status.

        @param name: Object name
        @param type: Object type
        @return: dict containing object context status information.
        '''
        ctx = {
            'application_name': self.name,
            'object_name': name,
            'object_type': type
        }
        return self._lcon.get_application_context_status([ctx])[0]

    def enable_ctx(self, name, type):
        '''
        Enable an application object context.

        @param name: Object name
        @param type: Object type
        '''
        ctx = {
            'application_name': self.name,
            'object_name': name,
            'object_type': type
        }
        self._lcon.enable_application_context_object([ctx])

    def disable_ctx(self, name, type):
        '''
        Disable an application object context.

        @param name: Object name
        @param type: Object type
        '''
        ctx = {
            'application_name': self.name,
            'object_name': name,
            'object_type': type
        }
        self._lcon.disable_application_context_object([ctx])

    @property
    def description(self):
        '''
        Lazy load application description value.

        @return: application description from the bigip.
        '''
        if not self._description:
            self._description = self._lcon.get_description([self.name])[0]

        return self._description

    @property
    def datacenters(self):
        '''
        Lazy load application datacenter list.

        @return: List of L{Datacenter} objects for this application.
        '''
        if not self._dcs:
            dcs = self._lcon.get_data_centers([self.name])[0]
            self._dcs = dict(((dc, Datacenter(self, dc)) for dc in dcs))

        return self._dcs

    def status(self):
        '''
        '''
        return self._lcon.get_object_status([self.name])[0]

    @property
    def wips(self):
        '''
        '''
        if not self._wips:
            self._wips = self._lcon.get_wide_ips([self.name])[0]

        return self._wips


class Datacenter(object):
    '''
    Application datacenter context object.
    '''
    _status = None

    def __init__(self, app, name):
        '''
        @param app: Containing application
        @param name: Datacenter name
        '''
        self._app = app
        self.name = name

    def enable(self):
        '''
        Enable this datacenter by enabling the coresponding application
        context object in the Application.
        '''
        self._app.enable_ctx(self.name,
                             'APPLICATION_OBJECT_TYPE_DATACENTER')

    def disable(self):
        '''
        Disable this datacenter by disabling the coresponding application
        context object in the Application.
        '''
        self._app.disable_ctx(self.name,
                              'APPLICATION_OBJECT_TYPE_DATACENTER')

    def toggle(self):
        '''
        Toggle enabled status
        '''
        self.enabled = not self.enabled

    def status(self):
        '''
        Get status information for this datacenter.
        '''
        return self._app.get_ctx(self.name,
                                 'APPLICATION_OBJECT_TYPE_DATACENTER')

    @property
    def enabled(self):
        '''

        @return: bool representation of datacenter enabled status.
        '''
        return self.status()['enabled_status'] == 'ENABLED_STATUS_ENABLED'

    @enabled.setter
    def enabled(self, value):
        '''
        Write property to allow setting the enable status for this datacenter.

        @param value: 
        '''
        value = bool(value)

        if value:
            self.enable()
        else:
            self.disable()
