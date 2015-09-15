# $Id: qWebUtils.py,v 1.11 2006/06/19 09:09:19 corva Exp $

'''Template support'''

import re, types, os, logging, qUtils
logger = logging.getLogger(__name__)

from PPA.Template.Controller import TemplateController, TemplateWrapper
from PPA.Template.Caches import MemoryCache, DummyCache
from PPA.Template.SourceFinders import FileSourceFinder, TemplateNotFoundError


class Writer:
    """Fast, but incompatible StringIO.StringIO implementation. Only supports
    write and getvalue methods"""

    def __init__(self):
        self.parts = []
        self.write = lambda s: self.parts.append(unicode(s))

    def getvalue(self):
        return ''.join(self.parts)


class _PPATemplateWrapper(TemplateWrapper):

    def __call__(self, namespace={}, **kwargs):
        fp = Writer()
        self.interpret(fp, namespace, kwargs)
        return fp.getvalue()


class TemplateGetter(object):

    _getters = {}

    def __new__(cls, search_dirs, cacheClass=MemoryCache):
        search_dirs = tuple(search_dirs)  # Insure sequence is immutable
        getter_key = (search_dirs,)
        if not cls._getters.has_key(getter_key):
            self = object.__new__(cls)
            self.source = search_dirs
            self.controller = TemplateController(
                    FileSourceFinder(search_dirs),
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


class Publisher(object):
    "Basic class for publishing. In general is inhereted"

    proxyClass = staticmethod(lambda x: x)
    renderHelperClass = RenderHelper
    templateDirs = None

    def __init__(self, site, **kwargs):
        self.site = site
        self.__dict__.update(kwargs)

    def globalNamespace(self):
        "Is used by RenderHelper, globalNamespace is passed to template"
        return self.site.globalNamespace
    globalNamespace = qUtils.CachedAttribute(globalNamespace)

    def getTemplate(self):
        "Is used by RenderHelper to find template"
        if self.templateDirs is None:
            return self.site.getTemplateGetter()
        else:
            return TemplateGetter(self.templateDirs)
    getTemplate = qUtils.CachedAttribute(getTemplate)


# vim: ts=8 sts=4 sw=4 ai et
