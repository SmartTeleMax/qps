# $Id: qSite.py,v 1.5 2004/04/07 15:30:46 ods Exp $

'''Classes for site as collection of streams'''

import types, sys, os, logging, weakref
logger = logging.getLogger(__name__)

import qBricks, qFieldTypes, qUtils


class StreamNotFoundError(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

class Site(object):
    '''Base class for site'''

    type = 'site'
    dbParams = {}
    streamDescriptions = None # Must be defined in child
    virtualStreamRules = []
    defaultStreamConf = qUtils.DictRecord(
        condition='', order='', group='', indexNum=0,
        brickDefaults={}, permissions=[], streamMakers=[], itemMakers=[],
        # itemMakeAction(item) -> {'make'|'delete'|None}
        # switches the behavior of maker.process()
        itemMakeAction=lambda i: 'make')
    title = host = None
    transmitTags = {'edit'  : 'edit',
                    'delete': 'all'}

    def globalNamespace(cls):
        from PPA.Template import Cook
        return {'quoteHTML'     : Cook.quoteHTML,
                'quoteFormField': Cook.quoteFormField,
                'quoteURLPath'  : Cook.quoteURLPath,
                'Cook'          : Cook}
    globalNamespace = qUtils.CachedClassAttribute(globalNamespace)
    
    templateDirs = []
    makeRoot = ''
    siteMakers = ['qps.qMake.StreamsMaker']
    # define charsets if you use runtime unicode strings
    templateCharset = clientCharset = dbCharset = None

    def __new__(selfclass):
        try:
            inst = selfclass.__inst__
        except AttributeError:
            selfclass.__inst__ = inst = object.__new__(selfclass)
            inst.init()
        return inst
    
    def init(self):
        logger.debug('Creating Site...')
        
        # status parameter
        self._retrieved = 0
        # caches
        self.streamCache = {}
        self.taggedStreamCache = {}
        self.streamList = {}
        # We don't need following code now, but it's can be useful in future
        #for cls in self.__class__.__bases__:
        #    if hasattr(cls, 'initMixIn'):
        #        cls.initMixIn(self)

    # For compatibility with stream/item interface
    def site(self):
        return self
    site = property(site)
    
    def createDBConnection(self):
        '''Default implementation creates connection to MySQL based on dbParams
        attribute of site.  Override this method to use another RDMS.'''
        from qDB.qMySQL import Connection
        return Connection(**self.dbParams)

    def dbConn(self):
        # We need this dispatch method to hide magic with CachedAttribute from
        # user.
        return self.createDBConnection()
    dbConn = qUtils.CachedAttribute(dbConn)

    maxAliasDepth = 5

    def streamFactory(self, stream_id, page=0, tag=None, **kwargs):
        params = {}
        try:
            # have we real stream with such id?
            stream_conf = self.streamDescriptions[stream_id]
        except KeyError:
            # no real stream - expand alias (look for virtual streams, if
            # supported)
            template_stream_id = stream_id
            for depth in range(self.maxAliasDepth):
                new_template_stream_id, new_params = \
                            self.expandStreamAlias(template_stream_id, tag)
                params.update(new_params)
                if new_template_stream_id==template_stream_id:
                    raise StreamNotFoundError(stream_id)
                else:
                    logger.debug('Virtual: %s -> %s', stream_id,
                                                      new_template_stream_id)
                try:
                    stream_conf = \
                        self.streamDescriptions[new_template_stream_id]
                except KeyError:
                    template_stream_id = new_template_stream_id
                else:
                    break
            else:
                raise RuntimeError('Maximum alias depth exceeded')
        if tag=='all':
            default_tag_params = {'condition': ''}
        else:
            default_tag_params = {}

        # keep tag in stream for use by fields
        kwargs['tag'] = tag

        # apply tagParams from all configuration parts
        result_conf = qUtils.DictRecord()
        for dict in self.defaultStreamConf, stream_conf, params, kwargs:
            tag_params = dict.get('tagParams', {}).get(tag, default_tag_params)
            result_conf = qUtils.DictRecord(result_conf, dict, tag_params)

        streamClassName = result_conf.streamClass
        if streamClassName:
            streamClass = self.getStreamClass(streamClassName)
        else:
            streamClass = qBricks.Stream
        return streamClass(self, stream_id, page, **result_conf)

    def retrieve(self, ignoreStatus=0):
        '''Retrieve (initialize) streams table'''
        if not self._retrieved or ignoreStatus:
            for stream_id in self.streamDescriptions.keys():
                self.streamList[stream_id] = self.retrieveStream(stream_id)
        self._retrieved = 1

    def __len__(self):
        self.retrieve()
        return len(self.streamList)

    def __iter__(self):
        self.retrieve()
        return self.streamList.itervalues()

    def transmitTag(self, tag):
        return self.transmitTags.get(tag, tag)

    def retrieveStream(self, stream_id, retrieve=0, tag=None):
        '''For internal use.  Retrieve description of one or all streams'''
        if tag is None:
            cache = self.streamCache
        else:
            cache = self.taggedStreamCache.setdefault(tag, {})
        if cache.has_key(stream_id):
            stream = cache[stream_id]
        else:
            stream = self.streamFactory(stream_id, tag=tag)
            cache[stream_id] = stream
        if retrieve:
            stream.retrieve()
        return stream

    def clear(self):
        '''Delete from cache all streams except marked as persistent'''
        streamCache = self.streamCache
        for name, stream in self.streamCache.items():
            if not getattr(stream, "persistent", None):
                del streamCache[name]
        self.taggedStreamCache.clear()
        self.streamList = {}

    def expandStreamAlias(self, stream_path, tag=None):
        '''Convert stream path to stream id (id of template stream) and
        additional parameters for stream initialization.  For real streams
        stream path is equal to stream id and there is no additional
        parameters.'''
        for stream_rec in self.virtualStreamRules:
            virtual = stream_rec.match(self, stream_path, tag)
            if virtual:
                virtual[1]['virtual'] = stream_rec                
                return virtual
        else:
            return stream_path, {}

    def getStreamClass(self, streamClassName):
        '''Return class of stream with name streamClassName.  Name must be a
        valid attribute of site or in form <ModuleName>.<ClassName>'''
        return qUtils.importObject(streamClassName, self)

    def getMakerClass(self, makerClassName):
        '''Return class of maker with name makerClassName.  Name must be a
        valid attribute of site or in form <ModuleName>.<ClassName>'''
        return qUtils.importObject(makerClassName, self)

    def getWriterClass(self, writerClassName):
        '''Return class of maker with name writerClassName.  Name must be a
        valid attribute of site or in form <ModuleName>.<ClassName>'''
        return qUtils.importObject(writerClassName, self)

    def getMaker(self, maker_desc, maker_params={}):
        if type(maker_desc) is str:
            name, params = maker_desc, maker_params
        else:
            name, params = maker_desc
            params = params.copy()
            params.update(maker_params)
        maker_class = self.getMakerClass(name)
        return maker_class(self, **params)

    def getWriter(self, writer_desc=None):
        if writer_desc is None:
            from qMake import Writer as writer_class
            params = {}
        else:
            if type(writer_desc) is str:
                name, params = (writer_desc, {})
            else:
                name, params = writer_desc
            writer_class = self.getWriterClass(name)
        return writer_class(self.makeRoot, charset=self.clientCharset,
                            **params)

    def getTemplateGetter(self, name=None):
        assert name is None  # No support for other getters in base class yet
        from qWebUtils import TemplateGetter
        return TemplateGetter(self.templateDirs, self.templateCharset)

    def makeAction(self):
        return 'make'

    def make(self, maker_params={}):
        '''Make all streams (i.e. make the whole site)'''

        makers = [self.getMaker(desc, maker_params) for desc in \
                  self.siteMakers]
        for maker in makers:
            maker.process(self)
        
    def path(self):
        return '/'


# vim: ts=8 sts=4 sw=4 ai et
