# -*- coding: koi8-r -*-

import logging
import qps, qps.qHTTP
import PPA.HTTP.Errors, PPA.Template.SourceFinders

logger = logging.getLogger(__name__)


class Error(PPA.HTTP.Errors.ClientError):
    def handle(self, request, response):
        PPA.HTTP.Errors.EndOfRequest.handle(self, request, response)
        response.setContentType(self._body_content_type)
        response.write(self.message)

def getException():
    from cStringIO import StringIO
    import traceback
    sio = StringIO()
    traceback.print_exc(file=sio)
    return sio.getvalue()


class Handler(qps.qHTTP.getAdapter()):
    noCache = False
    
    from PPA.HTTP.Errors import EndOfRequest, InternalServerError, \
         ClientError

    def __init__(self, commands, **kwargs):
        self.commands = commands
        self.__dict__.update(kwargs)
    
    def handle(self, request, response):
        if self.noCache:
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Expires'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
            
        self.commands.site.clear()    
        try:
            self.commands.handle(request, response)
        except self.ClientError, why:
            self.renderError(request, response, why)
        except (self.EndOfRequest, IOError):
            raise
        except:
            logger.exception('Unhandled exception for %s', request.uri())
            self.renderError(
                request, response,
                self.InternalServerError("<pre>%s</pre>" % getException())
                )

    def renderError(self, request, response, error, **kwargs):
        template = self.commands.renderHelperClass(
            self.commands, self.commands.getUser(request, response))
        try:
            body = template('errors/%s' % error.__class__.__name__,
                            error=error, brick=self.commands.site, **kwargs)
        except PPA.Template.SourceFinders.TemplateNotFoundError:
            raise error
        else:
            raise Error(error.status, message=body)
