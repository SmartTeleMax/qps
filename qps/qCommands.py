# $Id: qCommands.py,v 1.2 2004/03/18 15:27:35 ods Exp $

'''Framework for scripts with several commands (actions)'''

import logging
logger = logging.getLogger(__name__)

import qHTTP, qWebUtils


class BaseCommandDispatcher:
    '''Base class for commands based web-scripts.  Action is perfomed by
    calling do_<action>() method if this method exists or cmd_invalidCommand()
    if its absent.  If action is not specified the method cmd_defaultCommand()
    is called. All action methods are called with request, response and
    additional arguments.'''

    from PPA.HTTP.Errors import NotFound
    
    def dispatch(self, request, response, **kwargs):
        raise NotImplementedError

    def cmd_invalidCommand(self, request, response, *args, **kwargs):
        raise self.NotFound()
    
    def cmd_defaultCommand(self, request, response, *args, **kwargs):
        self.cmd_invalidCommand(request, response, *args, **kwargs)


class FieldNameCommandDispatcher(BaseCommandDispatcher):
    '''Base class for commands based web-scripts.  Action is determined from
    existing field names with certain prefix (field_name_prefix argument,
    default is 'action:').'''
    # <button> tag with fixed name and action in value is much better (no loop
    # over form field names), but cannot be used due to bug in the most popular
    # browser Internet Explorer.

    def dispatch(self, request, response, field_name_prefix='action:',
                 **kwargs):
        form = qHTTP.Form(request, self.getClientCharset(request))
        for field_name in form.keys():
            if field_name.startswith(field_name_prefix):
                action = field_name[len(field_name_prefix):]
                try:
                    method = getattr(self, 'do_'+action)
                except AttributeError:
                    logger.warn('Invalid command %r', action)
                    return self.cmd_invalidCommand(request, response, form,
                                                   **kwargs)
                else:
                    logger.debug('Dispatching for command %r', action)
                    return method(request, response, form, **kwargs)
        else:
            logger.debug('Assuming default command')
            return self.cmd_defaultCommand(request, response, form, **kwargs)


class PathInfoCommandDispatcher(BaseCommandDispatcher):
    '''Class for commands based web-scripts where action is determined from
    request.pathInfo.'''

    def dispatch(self, request, response, **kwargs):
        form = qHTTP.Form(request, self.getClientCharset(request))
        action = request.pathInfo[1:]
        if action:
            try:
                method = getattr(self, 'do_'+action)
            except AttributeError:
                method = self.cmd_invalidCommand
        else:
            method = self.cmd_defaultCommand
        return method(request, response, form, **kwargs)


class Publisher(qWebUtils.Publisher):
    from PPA.HTTP.Errors import SeeOther, NotFound, EndOfRequest, ClientError
    
    def showObject(self, request, response, obj, template_name,
                   content_type='text/html', **kwargs):
        template = self.renderHelperClass(self)
        
        response.setContentType(content_type,
                                charset=self.getClientCharset(request))
        response.write(template(template_name, brick=obj, **kwargs))

    def getClientCharset(self, request):
        '''Reload this method to determine charset per client'''
        return self.site.clientCharset

# vim: ts=8 sts=4 sw=4 ai et:
