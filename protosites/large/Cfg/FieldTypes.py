
from qps.qFieldTypes import *

class ORDER_NUM(INTEGER):
    default = 100
    max_value = 100
    permissions = []
    indexPermissions=[('all', 'rw')]
