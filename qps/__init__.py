# $Id: __init__.py,v 1.13 2004/10/07 14:35:20 ods Exp $

'''Q Publishing System
(c) 2000-2004 Sergey Barbarash, Oleg Broytmann, Pavel Barykin, Alexey
Melchakov, Denis Otkidach'''

__version__ = '2.6'

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

# vim: ts=8 sts=4 sw=4 ai et:
