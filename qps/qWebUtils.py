# $Id: qWebUtils.py,v 1.1.1.1 2004/03/18 15:17:17 ods Exp $

'''Template support'''

import re, types, os, logging, qUtils
logger = logging.getLogger(__name__)

from PPA.Template.Controller import TemplateController, TemplateWrapper
from PPA.Template.Caches import MemoryCache, DummyCache
from PPA.Template.SourceFinders import FileSourceFinder, TemplateNotFoundError
from StringIO import StringIO

class _PPATemplateWrapper(TemplateWrapper):
    
    def __call__(self, namespace={}, **kwargs):
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


class RenderHelper(object):
    def __init__(self, publisher):
        "Publisher is an object with getTemplate and globalNamespace attrs"
        self.publisher = publisher

    def __call__(self, template_name, **kwargs):
        ns = self.publisher.globalNamespace.copy()
        ns.update(kwargs)
        ns['template'] = self
        logger.debug('Rendering template %s', template_name)
        result = self.publisher.getTemplate(template_name)(ns)
        logger.debug('Finished rendering template %s', template_name)
        return result


class Publisher:

    proxyClass = lambda self, x: x
    renderHelper = RenderHelper
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
        return self.proxyClass(obj)

    def renderObject(self, obj, template_name, **kwargs):
        obj = self.prepareObject(obj)
        template = self.renderHelper(self)
        return template(template_name, brick=obj, **kwargs)


# vim: ts=8 sts=4 sw=4 ai et
