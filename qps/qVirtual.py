# $Id: qVirtual.py,v 1.3 2004/06/08 07:42:44 ods Exp $

'''Class for the most common virtual streams description rules'''

from qUtils import CachedAttribute, interpolateString

# Object describing rule for virtual streams must have methods:
#   matchParamStream(self, stream)  -> True if stream is stream of parameters
#                                      for this rule
#   match(site, stream_path)        -> None (if  stream_path is not covered by
#                                      this rule) or pair
#                                      (template_stream_id, parameters)
#   constructId(param_item)         -> stream_path
# and attributes:
#   paramName       - name of field in stream where parameter item will be
#                     stored
#   itemParamNames  - list of parameters to be initialized in item (default is
#                     [paramName])

class VirtualRule:
    '''Class for rules of virtual streams with single parameter.  Stream ID is
    formed as prefix+'/'+item_id_from_paramStream.  Default value for prefix is
    stream_id_of_paramStream.'''

    def defaultStreamParams(self):
        return {'streamMakers'  : [],
                'itemMakers'    : []}

    def __init__(self, templateStream, paramStream, paramName, prefix=None,
                 streamParams=None, titleTemplate=None):
        self.templateStream = templateStream
        self.paramStream = paramStream
        self.paramName = paramName
        self.titleTemplate = titleTemplate
        if prefix is None:
            self.prefix = paramStream
        else:
            self.prefix = prefix
        self.streamParams = self.defaultStreamParams()
        if streamParams:
            self.streamParams.update(streamParams)

    def itemParamNames(self):
        return [self.paramName]
    itemParamNames = property(itemParamNames)

    def matchParamStream(self, stream):
        return stream.id==self.paramStream

    def match(self, site, stream_path, tag=None):
        parts = stream_path.split('/')
        if len(parts)>=2 and '/'.join(parts[:-1])==self.prefix:
            param_stream = site.retrieveStream(self.paramStream,
                                               tag=site.transmitTag(tag))
            try:
                param_item_id = param_stream.itemIDField.convertFromString(
                                                                    parts[-1])
            except ValueError:
                return
            param_item = param_stream.retrieveItem(param_item_id)
            if param_item is None:
                # no such item
                return
            params = self.streamParams.copy()
            params[self.paramName] = param_item
            if self.titleTemplate is not None:
                params['title'] = interpolateString(self.titleTemplate, params)
            return self.templateStream, params
        else:
            return

    def constructId(self, param_item):
        return '%s/%s' % (self.prefix, param_item.id)

    def condition(self, stream):
        conn = stream.dbConn
        return conn.join(
                ['%s=%s' % (name, conn.convert(getattr(stream, name).id))
                             for name in self.itemParamNames])
        # XXX We must convert field with convertToDB
        # But there are problems with following code when many-to-many relation
        # is used. Try allStreamFields then use getattr(stream,
        # name).stream.itemIDField?
        #return conn.join(
        #        ['%s=%s' % (name,
        #                    conn.convert(
        #                        stream.allStreamFields[name].convertToDB(
        #                                            getattr(stream, name))))
        #         for name in self.itemParamNames])


CommonVirtualStream = VirtualRule

# vim: ts=8 sts=4 sw=4 ai et
