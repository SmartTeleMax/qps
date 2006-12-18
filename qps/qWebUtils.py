# $Id: qWebUtils.py,v 1.11 2006/06/19 09:09:19 corva Exp $

'''Template support'''

import re, types, os, logging, qUtils
logger = logging.getLogger(__name__)

from PPA.Template import FileSourceFinder, TemplateController, \
     TemplateNotFoundError


def buildTemplateController(search_dirs):
    """Returns PPA.Template.Controller.TemplateController instance, initialized
    to find templates in search_dirs"""
    
    source_finder = FileSourceFinder(search_dirs)
    controller = TemplateController(source_finder)
    return controller


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
        result = self.publisher.getTemplate(template_name).toString(ns)
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
            return buildTemplateController(self.templateDirs).getTemplate
    getTemplate = qUtils.CachedAttribute(getTemplate)


# vim: ts=8 sts=4 sw=4 ai et
