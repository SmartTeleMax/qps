# $Id: qPath.py,v 1.13 2004/03/16 15:48:21 ods Exp $

'''Standard QPS path parser'''

import logging
logger = logging.getLogger(__name__)


from qSite import StreamNotFoundError


class PathParser:

    def __init__(self, site, item_extensions=('html',),
                 index_file='index'):
        self.site = site
        self.item_extensions = item_extensions
        self.index_file = index_file

    def __call__(self, path, retrieve_stream=None):
        '''Return chain of matched objects.'''
        if retrieve_stream is None:
            retrieve_stream = self.site.retrieveStream
        if path in ('', '/'):
            return (self.site,)
        elif path[0]!='/':
            return (None,)
        elif path.endswith('/'):
            try:
                return (self.site, retrieve_stream(path[1:-1]))
            except StreamNotFoundError:
                return (self.site, None)
        else:
            pos = path.rfind('/')
            if pos<=0:
                return (self.site, None)
            try:
                stream = retrieve_stream(path[1:pos])
            except StreamNotFoundError:
                return (self.site, None, None)
            item_path = path[pos+1:]
            pos = item_path.rfind('.')
            if pos>=0 and (item_path[pos+1:] in self.item_extensions):
                item_id = item_path[:pos]
            else:
                item_id = item_path
            if item_id==self.index_file:
                return (self.site, stream)
            try:
                item_id = stream.itemIDField.convertFromString(item_id)
            except:
                return (self.site, stream, None)
            return (self.site, stream, stream.retrieveItem(item_id))


class PagedStreamLoader:

    def __init__(self, site, form, **params):
        self.site = site
        self.form = form
        self.params = params

    def __call__(self, stream_id, **params):
        try:
            page = int(self.form.getfirst('page', 1))
        except ValueError:
            page = 1
        if page<=0:
            page = 1
        _params = self.params.copy()
        _params.update(params)
        return self.site.streamFactory(stream_id, page=page, **_params)


class FilteredStreamLoader(PagedStreamLoader):

    # XXX
    '''WARNING! This is expirimental class. Its known to contain security
    vulnerabilities. Use it in your own risk.'''
    
    def __call__(self, stream_id):
        stream = PagedStreamLoader.__call__(self, stream_id)
        item = stream.createNewItem() # we need something to pass into
                                      # convert from form

        conds = []
        for field_name in self.form.keys():
            if field_name.startswith('qps-pattern:'):
                db_field = field_name[len('qps-pattern:'):]
                pattern = self.form.getfirst(field_name)
                if type(pattern) is unicode:
                    pattern = pattern.encode(self.site.dbCharset)
                conds.append("%s LIKE '%%%s%%'" % (
                    db_field,
                    stream.dbConn.escape(pattern))
                             )
            elif field_name.startswith('qps-exactmatch:'):
                db_field = field_name[len('qps-exactmatch:'):]
                field_type = stream.allItemFields[db_field]
                value = field_type.convertFromForm(self.form, field_name, item)
                conds.append("%s=%s" % \
                             (db_field, field_type.convertToDB(value, item))
                             )

        if conds:
            # we dont need paged stream anymore
            stream = self.site.streamFactory(stream_id, **self.params)
            for cond in conds:
                stream.addToCondition(cond)
        return stream 

# vim: ts=8 sts=4 sw=4 ai et
