# $Id: qVirtual.py,v 1.15 2005/08/13 00:04:57 corva Exp $

'''Class for the most common virtual streams description rules'''

from qUtils import CachedAttribute, interpolateString
from qDB.qSQL import Query, Param

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
    formed as prefix+item_id_from_paramStream+suffix, where 
    (prefix, suffix)=format.  If format is not set, then (paramStream+'/', '')
    assumed.'''

    def defaultStreamParams(self):
        return {'streamMakers'  : [],
                'itemMakers'    : []}

    def __init__(self, templateStream, paramStream, paramName, format=None,
                 prefix=None, # XXX deprecated, don't use it!
                 streamParams=None, titleTemplate=None):
        self.templateStream = templateStream
        self.paramStream = paramStream
        self.paramName = paramName
        self.titleTemplate = titleTemplate
        if format is None:
            self.prefix = (prefix or paramStream)+'/'
            self.suffix = ''
        else:
            self.prefix, self.suffix = format
        self.streamParams = self.defaultStreamParams()
        if streamParams:
            self.streamParams.update(streamParams)

    def itemParamNames(self):
        return [self.paramName]
    itemParamNames = property(itemParamNames)

    def matchParamStream(self, stream):
        return stream.id==self.paramStream

    def match(self, site, stream_path, tag=None):
        if stream_path.startswith(self.prefix) and \
                stream_path.endswith(self.suffix):
            param_item_id_str = stream_path[len(self.prefix):]
            if self.suffix:
                param_item_id_str = param_item_id_str[:-len(self.suffix)]
            param_stream = site.retrieveStream(self.paramStream,
                                               tag=site.transmitTag(tag))
            try:
                param_item_id = \
                    param_stream.fields.id.convertFromString(param_item_id_str,
                                                             param_stream)
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
        param_item_id_str = param_item.fields.id.convertToString(param_item.id,
                                                                 param_item)
        return '%s%s%s' % (self.prefix, param_item_id_str, self.suffix)

    def condition(self, stream):
        conn = stream.dbConn
        item = stream.createNewItem()
        conds = []
        for name in self.itemParamNames:
            param = getattr(stream, name)
            if stream.fields.has_key(name):
                param = stream.fields[name].convertToDB(param, item)
                conds.append(Query('%s.%s=' % (stream.tableName, name),
                                   Param(param)))
            else: # param is in join table
                param = param.fields.id.convertToDB(param.id, param)
                if hasattr(stream, 'joinTable'):
                    left = '%s.%s=' % (stream.joinTable, name)
                else:
                    # cant determine join table.. but it still may work
                    # if there are not field name collisions in joined tables
                    left = '%s=' % name
                conds.append(Query(left, Param(param)))
        return conn.join(conds)


# vim: ts=8 sts=4 sw=4 ai et
