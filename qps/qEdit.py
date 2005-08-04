# $Id: qEdit.py,v 1.32 2005/08/02 23:17:50 corva Exp $

'''Classes for editor interface.  For security resons usage of this module in
public scripts is not recommended.'''

import sys, types, os, Cookie, logging
from os.path import dirname, abspath

logger = logging.getLogger(__name__)
import qWebUtils, qSite, qHTTP, qUtils, qCommands, qPath, qSecurity


class RenderHelper(qWebUtils.RenderHelper):
    def __init__(self, edit, user, isNew=0, **kwargs):
        qWebUtils.RenderHelper.__init__(self, edit)
        self.edit = edit
        self.user = user
        self.isNew = isNew
        self.__dict__.update(kwargs)

    def fieldGlobalNamespace(self):
        namespace = self.edit.globalNamespace.copy()
        namespace['template'] = self
        return namespace
    fieldGlobalNamespace = qUtils.CachedAttribute(fieldGlobalNamespace)

    def allowedStreams(self):
        site = self.edit.site
        streams = []
        for stream_id, stream_conf in site.streamDescriptions.items():
            if self.user.checkPermission('x',
                                         stream_conf.get('permissions', [])):
                streams.append(site.createStream(stream_id, tag='edit'))
        return streams
    allowedStreams = qUtils.CachedAttribute(allowedStreams)

    def allowedFields(self, item):
        # assume item.type=='item'
        itemFieldsOrder = []
        for field_name, field_type in item.fields.iteritems():
            if self.isNew:
                permissions = field_type.createPermissions
            else:
                permissions = field_type.permissions
            perms = self.user.getPermissions(permissions)
            if ('w' in perms or 'r' in perms) and \
                   not (self.isNew and field_type.omitForNew):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def allowedIndexFields(self, stream):
        # assume stream.type=='stream':
        itemFieldsOrder = []
        if self.user.checkPermission('x', stream.permissions):
            for field_name, field_type in stream.indexFields.iteritems():
                if self.user.checkPermission('r', field_type.indexPermissions):
                    itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def isStreamUpdatable(self, stream):
        # assume stream.type=='stream':
        allowedIndexFields = self.allowedIndexFields(stream)
        if self.user.checkPermission('w', stream.permissions):
            item_fields = stream.indexFields
            for field_name in allowedIndexFields:
                field_type = item_fields[field_name]
                if self.user.checkPermission('w', field_type.indexPermissions):
                    return 1
        return 0

    def isStreamUnbindable(self, stream):
        return hasattr(stream, 'joinField') and \
                self.user.checkPermission('w',
                    stream.fields[stream.joinField].indexPermissions)

    def isStreamCreatable(self, stream):
        return self.user.checkPermission('c', stream.permissions)

    def isStreamDeletable(self, stream):
        return self.user.checkPermission('d', stream.permissions)

    def isItemPreviewable(self, item):
        """Returns is it possible to show preview page for brick or not.
        Preview page is available only for existing items, if stream has
        templateCat defined and Edit.showPreviews is True."""

        name = self.edit.previewTemplateName(item)
        if self.edit.showPreviews and not self.isNew and name:
            from PPA.Template.SourceFinders import TemplateNotFoundError
            try:
                self.edit.site.getTemplateGetter()(name)
            except TemplateNotFoundError:
                return False
            else:
                return True

    def bindingIndexFields(self, stream):
        # assume stream.type=='stream':
        itemFieldsOrder = []
        for field_name, field_type in stream.fields.iteritems():
            if field_type.showInBinding and \
                   self.user.checkPermission('r', field_type.indexPermissions):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def showField(self, item, name):
        '''Return representation of field in editor interface'''
        field_type = item.fields[name]
        stream_perms = self.user.getPermissions(item.stream.permissions)
        if self.isNew:
            permissions = field_type.createPermissions
        else:
            permissions = field_type.permissions
        perms = self.user.getPermissions(permissions)
        if 'w' in stream_perms and 'w' in perms:
            template_type = 'edit'
        elif 'r' in perms:
            template_type = 'view'
        else:
            return ''
        return field_type.show(item, name, template_type,
                               self.edit.getFieldTemplate,
                               self.fieldGlobalNamespace) # XXX namespace

    def showFieldInIndex(self, item, name, allow_edit=1):
        '''Return representation of field in stream'''
        stream = item.stream
        field_type = stream.indexFields[name]
        stream_perms = self.user.getPermissions(stream.permissions)
        perms = self.user.getPermissions(field_type.indexPermissions)
        if allow_edit and 'w' in stream_perms and 'w' in perms:
            template_type = 'edit'
        elif 'r' in perms:
            template_type = 'view'
        else:
            return ''
        template_type = 'index-' + template_type
        ns = self.fieldGlobalNamespace.copy()
        ns.update({'linkThrough': self.user.checkPermission(
            'r', item.permissions) and field_type.linkThrough})
        return field_type.show(item, name, template_type,
                               self.edit.getFieldTemplate,
                               ns) # XXX namespace

    def getPermissions(self, obj):
        return self.user.getPermissions(obj.permissions)

    getFieldPermissions = getPermissions

    def filterFields(self, stream):
        return hasattr(stream, 'filter') and \
               stream.filter.fields(stream) or []

    def showFilterField(self, item, name):
        '''Return representation of filter field'''

        field = item.stream.filter.createField(item.fields[name])
        return field.show(item, name, 'edit', # always editable
                          self.edit.getFieldTemplate,
                          self.fieldGlobalNamespace)


class EditBase:
    '''Base class for editor interface'''
    streamLoaderClass = qPath.PagedStreamLoader
    renderHelperClass = RenderHelper
    
    prefix = '/ed'
    templateDirs = ['%s/templates/default' % dirname(abspath(__file__))]
    fieldTemplateDirs = ['%s/fields' % dir for dir in templateDirs]
    securityGroupTable = {}

    delete_integrity_error = 'Some of objects you are trying to delete are ' \
                             'still referenced by other objects'
    view_denied_error = 'You have no permission to view this object'
    existing_id_error = 'Object with specified ID already exists'
    create_denied_error = 'You have no permission to create new object'
    edit_denied_error = 'You have no permission to edit this object'
    list_denied_error = 'You have no permission to list these objects'
    delete_denied_error = 'You have no permission to delete this object'
    invalid_command_message = 'Invalid action'
    
    item_extensions = ('html',)
    index_file = 'index'
    required_object_permission = {
        'stream': ('x', list_denied_error),
        'item': ('r', view_denied_error),
        'site': (None, None)
        }

    loggingStream = None # stream for user actions logging, see log method
    showPreviews = True # show brick previews

    def getFieldTemplate(self):
        return qWebUtils.TemplateGetter(self.fieldTemplateDirs,
                                        self.site.templateCharset)
    getFieldTemplate = qUtils.CachedAttribute(getFieldTemplate)

    def __init__(self, site):
        self.site = site
        self.parsePath = qPath.PathParser(site,
                                          item_extensions=self.item_extensions,
                                          index_file=self.index_file)

    def storableFields(self, item, user, isNew=0):
        itemFieldsOrder = []
        id_field_name = item.fields.idFieldName
        for field_name, field_type in item.fields.iteritems():
            if isNew:
                permissions = field_type.createPermissions
            else:
                permissions = field_type.permissions
            if field_name!=id_field_name and \
                    user.checkPermission('w', permissions):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def storableIndexFields(self, stream, user):
        itemFieldsOrder = []
        id_field_name = stream.fields.idFieldName
        for field_name, field_type in stream.indexFields.iteritems():
            if field_name!=id_field_name and \
                    user.checkPermission('w', field_type.indexPermissions):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def handle(self, request, response):
        form = qHTTP.Form(request, self.getClientCharset(request))
        user = self.getUser(request, response)
        objs = self.parsePath(request.pathInfo,
                              self.streamLoaderClass(self.site, form,
                                                     tag='edit'))
        if not user:
            self.cmd_notAuthorized(request, response, form, objs, user)
        if objs[-1] is None:
            raise self.NotFound()
        self.dispatch(request, response, field_name_prefix='qps-action:',
                      objs=objs, user=user)

    def log(self, user, command, params=None):
        if self.loggingStream:
            stream = self.site.retrieveStream(self.loggingStream)
            item = stream.createNewItem()
            item.user = user
            item.command = command
            item.params = params
            item.store()

    def showBrick(self, request, response, obj, user, isNew=0, **kwargs):
        template = self.renderHelperClass(self, user, isNew)
        response.setContentType('text/html',
                                charset=self.getClientCharset(request))
        response.write(template(obj.type, brick=obj, **kwargs))

    def cmd_defaultCommand(self, request, response, form, objs, user):
        '''Default action: show brick.'''
        obj = objs[-1]
        try:
            required_permission, error = \
                                 self.required_object_permission[obj.type]
        except KeyError:
            raise RuntimeError('Object of unexpected type %r' % obj.type)
        else:
            if required_permission and \
                    not user.checkPermission(required_permission,
                                             obj.permissions):
                raise self.ClientError(403, error)
        self.showBrick(request, response, obj, user)

    def cmd_invalidCommand(self, request, response, form, objs, user):
        raise self.ClientError(403, self.invalid_command_message)

    def do_newItem(self, request, response, form, objs, user):
        '''Show form for new item.  The path corresponds to stream in which
        item is intended to be created.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if not user.checkPermission('c', stream.permissions):
            raise self.ClientError(403, self.create_denied_error)
        item = stream.createNewItem(stream.fields.id.getDefault())
        self.showBrick(request, response, item, user, isNew=1)

    def do_createItem(self, request, response, form, objs, user):
        '''Create new item from form data.  The path corresponds to stream in
        which item is created.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if not user.checkPermission('c', stream.permissions):
            raise self.ClientError(403, self.create_denied_error)
        errors = {}
        id_field_type = stream.fields.id
        id_field_name = stream.fields.idFieldName
        if id_field_type.omitForNew:
            item_id = None
        else:
            try:
                item_id = id_field_type.convertFromForm(form, id_field_name)
            except id_field_type.InvalidFieldContent, exc:
                errors[id_field_name] = exc.message
                item_id = id_field_type.getDefault()
        item = stream.createNewItem(item_id)
        if not (id_field_type.omitForNew or errors) and item.exists()==1:
            raise self.ClientError(403, self.existing_id_error)
        errors.update(item.initFieldsFromForm(
                        form, names=self.storableFields(item, user, isNew=1)))
        if errors:
            for field_name, message in errors.items():
                logger.warning('Invalid content of field %r: %s',
                               field_name, message)
            return self.showBrick(request, response, item, user,
                                  isNew=1, fieldErrors=errors)
        else:
            item.store()
            self.log(user, 'createItem', {'item': item.path()})
            if item.existsInStream():
                raise self.SeeOther(self.prefix+item.path())
            else:
                raise self.SeeOther(self.prefix+item.stream.path())

    def do_updateItem(self, request, response, form, objs, user):
        '''Update existing item with form data.  The path corresponds to item
        being updated.'''
        import copy
        item = objs[-1]
        origitem = copy.copy(item)
        if item.type!='item':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if not user.checkPermission('w', item.stream.permissions):
            raise self.ClientError(403, self.edit_denied_error)
        errors = item.initFieldsFromForm(
                    form, names=self.storableFields(item, user))
        if errors:
            for field_name, message in errors.items():
                logger.warning('Invalid content of field %r: %s',
                               field_name, message)
            return self.showBrick(request, response, item, user,
                                  fieldErrors=errors)
        else:
            fields_to_store = []
            for field_name, field_type in item.fields.iteritems():
                if field_name!='id' and \
                        user.checkPermission('w', field_type.permissions):
                    fields_to_store.append(field_name)
            item.store(fields_to_store)
            changed = []
            for field in fields_to_store:
                if getattr(origitem, field) != getattr(item, field):
                    changed.append(field)
            self.log(user, "updateItem", {'item': item.path(),
                                          'fields': changed})
            if item.existsInStream():
                raise self.SeeOther(self.prefix+item.path())
            else:
                raise self.SeeOther(self.prefix+item.stream.path())

    def deleteItems(self, stream, form, user):
        '''Method to delete items from stream.  List of item IDs is taken from
        "qps-select" form field.'''
        if not user.checkPermission('d', stream.permissions):
            raise self.ClientError(403, self.delete_denied_error)
        item_ids = map(stream.fields.id.convertFromString,
                       form.getlist('qps-select'))
        if item_ids:
            try:
                stream.deleteItems(item_ids)
                self.log(user, 'deleteItems', {'stream': stream.path(),
                                               'items': item_ids})
            except stream.dbConn.IntegrityError:
                raise self.ClientError(403, self.delete_integrity_error)
    
    def do_deleteItems(self, request, response, form, objs, user):
        '''Delete item from stream.  The path corresponds to stream, from which
        items are deleted.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        self.deleteItems(stream, form, user)
        raise self.SeeOther(self.prefix+stream.path())

    def updateItems(self, stream, form, user):
        '''Method to update several items of stream at once.  Only changed
        fields are updated.  Names for fields are rewriten (in sense of
        field_type.convertFromForm()) from "name" to "qps-old:%s:%s" %
        (item.id, name) and "qps-new:%s:%s" % (item.id, name).'''
        if not user.checkPermission('w', stream.permissions):
            raise self.ClientError(403, self.edit_denied_error)
        updatable_fields = self.storableIndexFields(stream, user)
        item_fields = stream.indexFields
        if updatable_fields:
            item_id_strs = {}  # simulating set
            for name in form.keys():
                if name.startswith('qps-new:') or name.startswith('qps-old:'):
                    parts = name.split(':', 2)
                    if len(parts)!=3:
                        continue
                    item_id_strs[parts[1]] = 1
            for item_id_str in item_id_strs.keys():
                changed_fields = []
                item_id = stream.fields.id.convertFromString(item_id_str)
                item = stream.retrieveItem(item_id)
                if item is None:  # Somebody deleted it :)
                    continue
                for field_name in updatable_fields:
                    field_type = item_fields[field_name]
                    try:
                        old_value = field_type.convertFromForm(form,
                            ':'.join(['qps-old', item_id_str, field_name]),
                            item)
                        new_value = field_type.convertFromForm(form,
                            ':'.join(['qps-new', item_id_str, field_name]),
                            item)
                        if new_value!=old_value:
                            setattr(item, field_name, new_value)
                            changed_fields.append(field_name)
                    except field_type.InvalidFieldContent, exc:
                        logger.warning(
                                'Error in updateItems for field %s: %s',
                                field_name, exc.message)
                if changed_fields:
                    item.store(changed_fields)
                    self.log(user, 'updateItems', {'item': item.path(),
                                                   'fields': changed_fields})

    def do_updateItems(self, request, response, form, objs, user):
        '''Update several items of stream.  The path corresponds to stream, of
        which items are updated.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        self.updateItems(stream, form, user)
        raise self.SeeOther(self.prefix+stream.path())
    
    def do_unbindItems(self, request, response, form, objs, user):
        '''Unbind several items from virtual (many-to-many) stream.  The path
        corresponds to stream, from which items are unbound.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_name = getattr(stream, 'joinField', None)
        if field_name is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_type = stream.fields[field_name]
        if not (user.checkPermission('w', stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        binding_to_item = getattr(stream, stream.virtual.paramName)
        item_ids = map(stream.fields.id.convertFromString,
                       form.getlist('qps-select'))
        for item_id in item_ids:
            item = stream.retrieveItem(item_id)
            values = getattr(item, field_name)
            values = [value for value in values
                      if value!=binding_to_item]
            setattr(item, field_name, values)
            item.store([field_name])
            self.log(user, 'unbindItems', {'item': item.path(),
                                           'field': field_name})
        raise self.SeeOther(self.prefix+stream.path())

    def do_showBinding(self, request, response, form, objs, user):
        '''List items that can be bound to some virtual stream.  The path
        corresponds to template stream (stream of items suitable to bind).  The
        form field "bound" must contain path for virtual stream to bind to or
        path for item and name of its field of type EXT_FOREIGN_MULTISELECT in
        form field "field".'''
        template_stream = objs[-1]
        if template_stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        bound_path = form.getfirst('bound')
        if bound_path is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        bound_objs = self.parsePath(bound_path,
               lambda stream_id: self.site.retrieveStream(stream_id,
                                                          tag='edit'))
        bound = bound_objs[-1]
        if bound is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if bound.type=='stream':
            field_name = getattr(bound, 'joinField', None)
            binding_to_item = getattr(bound, bound.virtual.paramName)
            is_bound = lambda item: binding_to_item in getattr(item, field_name)
            bound_stream = bound
            bound_element_type = "checkbox"
        elif bound.type=='item':
            field_name = form.getfirst('field')
            binding_to_item = bound
            field = getattr(binding_to_item, field_name)
            try:
                iter(field)
            except TypeError: # field is not a sequence
                is_bound = lambda item: item==field
                bound_element_type = "radio"
            else:             # field is a sequence
                is_bound = lambda item: item in field
                bound_element_type = "checkbox"
            bound_stream = bound.stream
        else:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if field_name is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_type = bound_stream.fields[field_name]
        if not (user.checkPermission('w', bound_stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        template = self.renderHelperClass(self, user)
        response.setContentType('text/html',
                                charset=self.getClientCharset(request))
        response.write(template('binding', brick=template_stream,
                                item=binding_to_item, fieldName=field_name,
                                bound=bound, boundPath=bound_path,
                                isBound=is_bound,
                                boundElementType=bound_element_type,
                                updated=form.getfirst('updated')))

    def do_updateBinding(self, request, response, form, objs, user):
        '''Store new binding.  The path corresponds to template stream (stream
        of items suitable to bind).  The form field "bound" must contain path
        for virtual stream to bind to or path for item and name of its field of
        type EXT_FOREIGN_MULTISELECT in form field "field".'''
        template_stream = objs[-1]
        if template_stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        bound_path = form.getfirst('bound')
        if bound_path is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        bound_objs = self.parsePath(bound_path,
               lambda stream_id: self.site.retrieveStream(stream_id,
                                                          tag='edit'))
        bound = bound_objs[-1]
        if bound is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if bound.type=='stream':
            field_name = getattr(bound, 'joinField', None)
            binding_to_item = getattr(bound, bound.virtual.paramName)
            bound_stream = bound
        elif bound.type=='item':
            field_name = form.getfirst('field')
            binding_to_item = bound
            bound_stream = bound.stream
        else:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if field_name is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_type = bound_stream.fields[field_name]
        if not (user.checkPermission('w', bound_stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        convert = template_stream.fields.id.convertFromString
        old_ids = map(convert, form.getlist('qps-old'))
        new_ids = map(convert, form.getlist('qps-new'))
        if bound.type=='stream':  # direct binding
            for item_id in old_ids:
                if item_id not in new_ids:
                    item = template_stream.retrieveItem(item_id)
                    values = getattr(item, field_name)
                    values = [value for value in values
                              if value!=binding_to_item]
                    setattr(item, field_name, values)
                    item.store([field_name])
            for item_id in new_ids:
                if item_id not in old_ids:
                    item = template_stream.retrieveItem(item_id)
                    values = getattr(item, field_name)
                    values.append(binding_to_item)
                    setattr(item, field_name, values)
                    item.store([field_name])
                    self.log(user, 'updateBinding', {'item': item.path(),
                                                     'field': field_name})
        else:  # reverse binding
            field = getattr(bound, field_name)
            try:
                iter(field)
            except TypeError: # field is not a sequence
                new_id = new_ids and new_ids[0] or None
                value = field
                if new_id and (not value or value.id != new_id):
                    setattr(bound, field_name,
                            template_stream.retrieveItem(new_id))
                    bound.store([field_name])
            else:             # field is a sequence
                values = list(field)
                for item_id in old_ids:
                    if item_id not in new_ids:
                        values = [value for value in values
                                  if value.id!=item_id]
                for item_id in new_ids:
                    if item_id not in old_ids:
                        item = template_stream.retrieveItem(item_id)
                        values.append(item)
                if values!=getattr(bound, field_name):
                    setattr(bound, field_name, values)
                    bound.store([field_name])
                    self.log(user, 'updateBinding', {'item': bound.path(),
                                                     'field': field_name})
        raise self.SeeOther(
            '%s%s?qps-action%%3AshowBinding=1&bound=%s&field=%s&page=%s' \
            '&updated=1' % (self.prefix, template_stream.path(), bound.path(),
                            field_name, template_stream.page))

    def do_showField(self, request, response, form, objs, user):
        "Shows field like publisher.showField does"
        
        item = objs[-1]
        if item.type != 'item':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        template = self.renderHelperClass(self, user, isNew=False)
        fieldName = form.getfirst('field', '')

        response.setContentType('text/html',
                                charset=self.getClientCharset(request))
        response.write(template.showField(item, fieldName))

    def previewTemplateName(self, brick):
        """Returns preview template name for brick or None if
        templateName is not available"""
        
        templateCat = hasattr(brick, 'templateCat') and brick.templateCat or \
                      (hasattr(brick, 'stream') and \
                       hasattr(brick.stream, 'templateCat')) and \
                       brick.stream.templateCat
        if templateCat:
            return "%s.%s" % (templateCat, brick.type)

    def do_showItemPreview(self, request, response, form, objs, user):
        """Inits item fields from form and shows preview page"""
        
        item = objs[-1]
        errors = item.initFieldsFromForm(
                    form, names=self.storableFields(item, user))
        if errors:
            for field_name, message in errors.items():
                logger.warning('Invalid content of field %r: %s',
                               field_name, message)
            return self.showBrick(request, response, item, user,
                                  fieldErrors=errors)
        else:
            publisher = qWebUtils.Publisher(self.site)
            template = qWebUtils.RenderHelper(publisher)
            response.setContentType('text/html',
                                    charset=self.getClientCharset(request))
            response.write(template(self.previewTemplateName(item),
                                    brick=item))


class Edit(EditBase, qCommands.Publisher, qCommands.FieldNameCommandDispatcher,
           qSecurity.BasicAuthHandler):
    pass

# vim: ts=8 sts=4 sw=4 ai et
