'''Q Publishing System

Copyright (c) 2000-2004 Sergey Barbarash, Oleg Broytman, Pavel Barykin,
Alexey Melchakov, Denis Otkidach.

Copyright (c) 2005 Alexey Melchakov, Denis Otkidach.

Copyright (c) 2006, 2007 Olga Sorokina, Alexey Melchakov, Denis Otkidach.

Copyright (c) 2013-2015 Oleg Broytman.

'''

__version__ = '2.9'

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
