# $Id: qCommands.py,v 1.14 2006/10/05 14:42:30 olga_sorokina Exp $

'''Framework for scripts with several commands (actions)'''

import logging
logger = logging.getLogger(__name__)

import qHTTP, qWebUtils, qUtils


class BaseCommandDispatcher:
    '''Base class for commands based web-scripts.  Action is perfomed by
    calling do_<action>() method if this method exists or cmd_invalidCommand()
    if its absent.  If action is not specified the method cmd_defaultCommand()
    is called. All action methods are called with request, response and
    additional arguments.'''

    def __call__(self, publisher, request, response, form, **kwargs):
        """Is called by publisher, dispatches request to method"""
        command, params = self.parseRequest(publisher, request, response, form,
                                            **kwargs)
        if command:
            try:
                method = getattr(publisher, 'do_'+command)
            except AttributeError:
                logger.warn('Invalid command %r', command)
                method = publisher.cmd_invalidCommand
            else:
                logger.debug('Dispatching for command %r', command)
        else:
            logger.debug('Assuming default command')
            method = publisher.cmd_defaultCommand
        kwargs.update(params)
        return method(request, response, form, **kwargs)

    def parseRequest(self, publisher, request, response, form, **kwargs):
        '''Parses request and returns (command, params) pair (empty string or
        None means default command)'''
        raise NotImplementedError

    def addCommand(self, url, cmd):
        "Adds command to url"
        raise NotImplementedError


class FieldNameCommandDispatcher(BaseCommandDispatcher):
    '''Base class for commands based web-scripts.  Action is determined from
    existing field names with certain prefix (field_name_prefix argument,
    default is 'action:').'''
    # <button> tag with fixed name and action in value is much better (no loop
    # over form field names), but cannot be used due to bug in the most popular
    # browser Internet Explorer.

    def __init__(self, field_name_prefix):
        self.field_name_prefix = field_name_prefix

    def parseRequest(self, publisher, request, response, form, **kwargs):
        for field_name in form.keys():
            if field_name.startswith(self.field_name_prefix):
                return field_name[len(self.field_name_prefix):], {}
        else:
            return None, {}

    def addCommand(self, url, cmd):
         sep = '?' in url and '&' or '?'
         return "%s%s%s%s=1" % (url, sep, self.field_name_prefix, cmd)


class FieldCommandDispatcher(BaseCommandDispatcher):
    '''Class for commands based web-scripts. Action is determined from
    field "qps-action" or is passed to dipatch method'''

    def __init__(self, field_name):
        self.field_name = field_name

    def parseRequest(self, publisher, request, response, form, **kwargs):
        return form.getfirst(self.field_name), {}

    def addCommand(self, url, cmd):
        sep = '?' in url and '&' or '?'
        return "%s%s%s=%s" % (url, sep, self.field_name, cmd)


class PathInfoCommandDispatcher(BaseCommandDispatcher):
    '''Class for commands based web-scripts where action is determined from
    request.pathInfo.'''

    def parseRequest(self, publisher, request, response, form, **kwargs):
        return request.pathInfo[1:], {}

    def addCommand(self, url, cmd):
        sep = not url.endswith('/') and '/' or ''
        return "%s%s%s" % (url, sep, cmd)


class Publisher(qWebUtils.Publisher):
    "Basic web publisher. Handle method must be implemented by user."

    from PPA.HTTP.Errors import SeeOther, NotFound, EndOfRequest, ClientError

    def handle(self, request, response):
        """Is called by PPA.HTTP.Base.Adapter.__call__"""
        raise NotImplementedError

    def showObject(self, request, response, template_name,
                   content_type='text/html', **kwargs):
        """Renders template and writes it to response,

        template_name is a name of template
        content_type is passed to respose.setContentType
        keyword arguments are passed to template"""

        template = self.renderHelperClass(self)
        response.setContentType(content_type,
                                charset=self.getClientCharset(request))
        response.write(template(template_name, **kwargs))

    def getClientCharset(self, request):
        '''Reload this method to determine charset per client'''
        return self.site.clientCharset


class DispatchedPublisher(Publisher):
    """Dispatches requests to methods using self.dispatcher"""

    dispatcher = FieldNameCommandDispatcher(field_name_prefix='qps-action:')

    def cmd_invalidCommand(self, request, response, *args, **kwargs):
        """Is called when dispatcher was unable to find method to call"""
        raise self.NotFound()

    def cmd_defaultCommand(self, request, response, *args, **kwargs):
        """Is called when no action was given to dispatcher"""
        self.cmd_invalidCommand(request, response, *args, **kwargs)

    def handle(self, request, response):
        "Dispatches requests with self.dispatcher to methods"
        form = qHTTP.Form(request, self.getClientCharset(request))
        self.dispatcher(self, request, response, form)


# vim: ts=8 sts=4 sw=4 ai et:
