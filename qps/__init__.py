# $Id: __init__.py,v 1.16 2005/08/18 02:12:28 corva Exp $

'''Q Publishing System
(c) 2000-2004 Sergey Barbarash, Oleg Broytmann, Pavel Barykin, Alexey
Melchakov, Denis Otkidach'''

__version__ = '2.8'

import logging

def configLogger(
        format='%(asctime)s: %(levelname)-5s: %(name)-15s: %(message)s',
        level=logging.INFO, handler=None):

    logging.root.handlers = []
    if handler is None:
        handler = logging.StreamHandler()
    formatter = logging.Formatter(format)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(level)

# vim: ts=8 sts=4 sw=4 ai et:
