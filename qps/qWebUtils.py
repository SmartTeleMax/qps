# $Id: qWebUtils.py,v 1.5 2004/06/08 10:30:31 corva Exp $

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
        getter_key = (search_dirs, charset)
        if not cls._getters.has_key(getter_key):
            self = object.__new__(cls)
            self.source = search_dirs
            self.controller = TemplateController(
                    FileSourceFinder(search_dirs,
                                     file=qUtils.ReadUnicodeFile(charset)),
                    template_wrapper_class=_PPATemplateWrapper,
                    template_cache=cacheClass())
            cls._getters[getter_key] = self
        return cls._getters[getter_key]

    def __call__(self, template_name, template_type=None):
        logger.debug('Getting template %s from %s',
                     template_name, self.source)
        template = self.controller.getTemplate(template_name, template_type)
        logger.debug('Template has type %s', template.type)
        return template


class RenderHelper(object):
    """RenderHelper class, common usage is:

    renderer = RenderHelper(publisher)
    renderer('template_name', **kwargs)

    Publisher is an object with getTemplate and globalNamespace attributes

    Template, addressed by name 'template_name' is rendered by calling
    renderer, kwargs are passed to template as global vars, moreover,
    renderer object appears in template's global vars as 'template'"""

    def __init__(self, publisher):
        "Publisher is an object with getTemplate and globalNamespace attrs"
        self.publisher = publisher

    def __call__(self, template_name, **kwargs):
        "Interprets template named template_name and returns result string"
        ns = self.publisher.globalNamespace.copy()
        ns.update(kwargs)
        ns['template'] = self
        logger.debug('Rendering template %s', template_name)
        result = self.publisher.getTemplate(template_name)(ns)
        logger.debug('Finished rendering template %s', template_name)
        return result


class Publisher:

    proxyClass = staticmethod(lambda x: x)
    renderHelperClass = RenderHelper
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


# vim: ts=8 sts=4 sw=4 ai et
