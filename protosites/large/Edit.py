import logging

import qps, qps.qHTTP
import Site

logger = logging.getLogger(__name__)

Adapter = qps.qHTTP.getAdapter()
class Handler(Adapter):
    from PPA.HTTP.Errors import EndOfRequest, InternalServerError
    
    def handle(self, request, response):
        self.__commands.site.clear()
        
        try:
            self.__commands.handle(request, response)
        except (self.EndOfRequest, IOError):
            raise
        except self.__commands.site.dbConn.OperationalError:
            logger.exception('Unhandled exception for %%s', request.uri())
            self.reportException(response)
        except:
            logger.exception('Unhandled exception for %%s', request.uri())
            self.reportException(response)

    def reportException(self, response, site):
        raise self.InternalServerError("<pre>%%s</pre>" %% self.getException())

    def getException(self):
        from cStringIO import StringIO
        import traceback

        sio = StringIO()
        traceback.print_exc(file=sio)
        return sio.getvalue()
