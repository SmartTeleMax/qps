# $Id: qUtils.py,v 1.10 2007/02/07 14:23:57 ods Exp $

'''Miscellaneous utilities'''

import os, logging, sys, weakref
logger = logging.getLogger(__name__)

def writeFile(file_name, data):
    '''Write data to file with full path file_name, creating if needed
    intermediate directories'''
    logger.info('Writing %s', file_name)
    dir_name = os.path.dirname(file_name)
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
    temp_file_name = file_name+'.new~'
    fp = open(temp_file_name, 'wb')
    try:
        fp.write(data)
    finally:
        fp.close()
    os.rename(temp_file_name, file_name)


class ReadUnicodeFile:
    def __init__(self, charset):
        self._charset = charset

    def __call__(self, path):
        if self._charset:
            import codecs
            return codecs.getreader(self._charset)(file(path))
        else:
            return file(path)


def importModule(name, globals=None):
    parts = name.split('.')
    module = __import__(name, globals)
    for part in parts[1:]:
        module = getattr(module, part)
    return module

    
def importObject(name, default_module=None, globals=None):
    '''Import object with name in form package.module.obj_name'''
    if '.' in name:
        parts = name.split('.')
        obj_name = parts[-1]
        obj = __import__('.'.join(parts[:-1]), globals)
        for part in parts[1:]:
            obj = getattr(obj, part)
        return obj
    else:
        return getattr(default_module, name)


class DictImporter:

    def __init__(self, package=None, name=None):
        if package:
            self._template = package+'.%s'
        else:
            self._template = '%s'
        if name:
            self._template += '.'+name
            self._import = importObject
        else:
            self._import = importModule
        self._globals = sys._getframe(1).f_globals
        self._cache = {}
        self._missing = object()

    def _retrieve(self, module_name):
        if not self._cache.has_key(module_name):
            try:
                self._cache[module_name] = self._import(
                    self._template % module_name,
                    globals = self._globals)
            except (ImportError, AttributeError):
                self._cache[module_name] = self._missing
        return self._cache[module_name]

    def __getitem__(self, module_name):
        value = self._retrieve(module_name)
        if value is self._missing:
            raise KeyError(module_name)
        else:
            return value

    def get(self, module_name, default=None):
        value = self._retrieve(module_name)
        if value is self._missing:
            return default
        else:
            return value


class CachedAttribute(object):

    def __init__(self, method, name=None):
        self.method = method
        self.name = name or method.__name__

    def __get__(self, inst, cls):
        if inst is None:
            return self
        try:
            result = self.method(inst)
            setattr(inst, self.name, result)
        except:
            # XXX It's a bug in Python 2.2: any exception is replaced with
            # AttributeError
            logger.exception('Error in CachedAttribute:')
            raise
        return result


class CachedClassAttribute(object):

    def __init__(self, method, name=None):
        self.method = method
        self.name = name or method.__name__

    def __get__(self, inst, cls):
        try:
            result = self.method(cls)
            setattr(cls, self.name, result)
        except:
            # XXX It's a bug in Python 2.2: any exception is replaced with
            # AttributeError
            logger.exception('Error in CachedClassAttribute:')
            raise
        return result


class ReadAliasAttribute(object):

    def __init__(self, name):
        self.name = name

    def __get__(self, inst, cls):
        if inst is None:
            return self
        return getattr(inst, self.name)


class AliasAttribute(ReadAliasAttribute):

    def __set__(self, inst, value):
        setattr(inst, self.name, value)

    def __delete__(self, inst):
        delattr(inst, self.name)


class DictRecord(dict):
    '''Handy class providing two ways to get/set items.'''
    def __init__(self, *args, **kwargs):
        dict.__init__(self)
        for arg in args+(kwargs,):
            self.update(arg)
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value


class Descriptions(object):
    """Dictionary-like storage for ordered config.

    Usage:

        config = Descriptions([name1, config,
                               name2, config,
                               ...])"""

        
    
    def __init__(self, config):
        self._config = config

    def __repr__(self):
        return repr(self._config)

    def __nonzero__(self):
        return self._config and True or False

    def __iter__(self):
        return iter(self._config)

    def __add__(self, other):
        return self.__class__(self._config + other._config)

    def iteritems(self):
        return iter(self._config)

    def iterkeys(self):
        for fn, ft in self:
            yield fn

    def items(self):
        return self._config[:]

    def keys(self):
        return [fn for fn, ft in self]

    def values(self):
        return [ft for fn, ft in self]
    
    def _config_dict(self):
        return dict(self._config)
    _config_dict = CachedAttribute(_config_dict, '_config_dict')

    def has_key(self, field_name):
        return self._config_dict.has_key(field_name)

    def __setitem__(self, name_for_update, value_for_update):
        for pos, (field_name, field_value) in enumerate(self._config):
            if field_name == name_for_update:
                self._config[pos] = (field_name, value_for_update)
                break
        else:
            raise KeyError(name_for_update)
        # clear cache
        try:
            del self._config_dict
        except AttributeError:
            pass

    def __getitem__(self, name):
        return self._config_dict[name]
    
    def get(self, field_name, default=None):
        return self._config_dict.get(field_name, default)


class ObjectDict:
    def __init__(self, obj):
        self.__obj = obj
    def __getitem__(self, key):
        try:
            return getattr(self.__obj, key)
        except AttributeError:
            raise KeyError(key)


from PPA.Template.Engines.PySI import EvalDict

def interpolateString(template, namespace):
    return template % EvalDict({}, namespace)


def createWeakProxy(obj):
    "Returns weakref.proxy of obj"
    
    try:
        return weakref.proxy(obj)
    except TypeError: # obj already is a proxy
        return obj

# vim: ts=8 sts=4 sw=4 ai et
