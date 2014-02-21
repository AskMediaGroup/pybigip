'''
pybigip - A library for managing f5 bigip appliances.
'''


from bigsuds import BIGIP


class Connection(BIGIP):
    '''
    Wrapper around bigsuds connection class to help abstract us from future
    backend library changes (iControl REST?).
    '''
