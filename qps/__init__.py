# $Id: __init__.py,v 1.2 2004/04/19 15:33:29 ods Exp $

'''Q Publishing System
(c) 2000-2004 Sergey Barbarash, Oleg Broytmann, Pavel Barykin, Alexey
Melchakov, Denis Otkidach'''

__version__ = '2.4+'

import logging

def configLogger(
        format='%(asctime)s: %(levelname)-5s: %(name)-15s: %(message)s',
        level=logging.INFO, handler=None):
    if not logging.root.handlers:
        if handler is None:
            handler = logging.StreamHandler()
        formatter = logging.Formatter(format)
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
    logging.root.setLevel(level)

from mx.Misc.LazyModule import LazyModule

qVirtual = LazyModule('qVirtual', locals(), globals())
qMake = LazyModule('qMake', locals(), globals())
qBricks = LazyModule('qBricks', locals(), globals())
qSite = LazyModule('qSite', locals(), globals())
qEdit = LazyModule('qEdit', locals(), globals())
qFilters = LazyModule('qFilters', locals(), globals())
qHTTP = LazyModule('qHTTP', locals(), globals())

# vim: ts=8 sts=4 sw=4 ai et:
