# $Id: qWebUtils.py,v 1.59 2004/03/16 15:48:21 ods Exp $

'''Template support'''

import re, types, os, logging, qUtils
logger = logging.getLogger(__name__)

from PPA.Template.Controller import TemplateController, TemplateWrapper
from PPA.Template.Caches import MemoryCache, DummyCache
from PPA.Template.SourceFinders import FileSourceFinder, TemplateNotFoundError
from StringIO import StringIO

class _PPATemplateWrapper(TemplateWrapper):
    
    def __call__(self, object=None, namespace={}, **kwargs):
        namespace = namespace.copy()
        kwargs['brick'] = kwargs['__object__'] = object
        fp = StringIO()
        self.interpret(fp, namespace, kwargs)
        return fp.getvalue()
        
try:
    import _apache
except ImportError:
    cacheClass = MemoryCache
else:
    cacheClass = DummyCache


class TemplateGetter(object):

    _getters = {}
    
    def __new__(cls, search_dirs, charset=None):
        search_dirs = tuple(search_dirs)  # Insure sequence is immutable
        getter_key = (tuple(search_dirs), charset)
        if not cls._getters.has_key(getter_key):
            self = object.__new__(cls)
            self.search_dirs = search_dirs
            self.controller = TemplateController(
                    FileSourceFinder(search_dirs,
                                     file=qUtils.ReadUnicodeFile(charset)),
                    template_wrapper_class=_PPATemplateWrapper,
                    template_cache=cacheClass())
            cls._getters[getter_key] = self
        return cls._getters[getter_key]

    def __call__(self, template_name, template_type=None):
        logger.debug('Getting template %s from %s',
                     template_name, self.search_dirs)
        template = self.controller.getTemplate(template_name, template_type)
        logger.debug('Template has type %s', template.type)
        return template


class MakedObject:
    '''Wrapper class to add templating tools to made object.
    Positional arguments:
        object           - object to be made;
        template_getter  - function (or other callable object) implementing
                           template lookup, default looks for templates in
                           base_dir+'./template';
    Keyword arguments:
        global_namespace - global namespace for template,
        **kwargs         - other parameters.
    '''

    def __init__(self, object, template_getter, global_namespace={}, **kwargs):
        self.object = object
        self.getTemplate = template_getter
        self.globalNamespace = global_namespace
        self.__dict__.update(kwargs)

    def __getattr__(self, attr_name):
        return getattr(self.object, attr_name)

    def template(self, template_name, brick=None, **kwargs):
        # Notice, brick have to be already wrapped with MakedObject
        if brick is None:
            brick = self
        name_space = self.globalNamespace.copy()
        name_space.update(kwargs)
        logger.debug('Rendering template %s', template_name)
        result = self.getTemplate(template_name)(brick, name_space)
        logger.debug('Finished rendering template %s', template_name)
        return result
        

class Publisher:

    proxyClass = MakedObject
    templateDirs = None

    def __init__(self, site):
        self.site = site

    def globalNamespace(self):
        return self.site.globalNamespace
    globalNamespace = qUtils.CachedAttribute(globalNamespace)

    def getTemplate(self):
        if self.templateDirs is None:
            return self.site.getTemplateGetter()
        else:
            return TemplateGetter(self.templateDirs, self.site.templateCharset)
    getTemplate = qUtils.CachedAttribute(getTemplate)

    def prepareObject(self, obj):
        return self.proxyClass(obj, template_getter=self.getTemplate,
                               global_namespace=self.globalNamespace)

    def renderObject(self, obj, template_name, **kwargs):
        obj = self.prepareObject(obj)
        return obj.template(template_name, **kwargs)


# vim: ts=8 sts=4 sw=4 ai et
