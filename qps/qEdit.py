# $Id: qEdit.py,v 1.5 2004/04/07 18:52:49 corva Exp $

'''Classes for editor interface.  For security resons usage of this module in
public scripts is not recommended.'''

import sys, types, os, Cookie, logging
from os.path import dirname, abspath

logger = logging.getLogger(__name__)
import qWebUtils, qSite, qHTTP, qUtils, qCommands, qPath, qSecurity

class MakedEditObject(qWebUtils.MakedObject):
    "Wrapper class to add templating tools to made object for editor interface"
    
    def __init__(self, object, template_getter,
                 field_template_getter, global_namespace={}, **kwargs):
        qWebUtils.MakedObject.__init__(self, object, template_getter,
                                       global_namespace, **kwargs)
        self.getFieldTemplate = field_template_getter

    def fieldGlobalNamespace(self):
        namespace = self.globalNamespace.copy()
        namespace['edPrefix'] = self.edPrefix
        namespace['edUser'] = self.edUser
        namespace['isNew'] = self.isNew
        return namespace
    fieldGlobalNamespace = qUtils.CachedAttribute(fieldGlobalNamespace)

    def allowedStreams(self):
        site = self.object.site
        streams = []
        for stream_id, stream_conf in site.streamDescriptions.items():
            if self.edUser.checkPermission('x',
                                           stream_conf.get('permissions', [])):
                streams.append(site.streamFactory(stream_id, tag='edit'))
        return streams
    allowedStreams = qUtils.CachedAttribute(allowedStreams)

    def getAllowedFields(self, obj=None):
        if obj is None:
            obj = self.object
        # assume obj.type=='item'
        stream = obj.stream
        item_fields = stream.allItemFields
        itemFieldsOrder = []
        for field_name in ['id']+stream.itemFieldsOrder:
            field_type = item_fields[field_name]
            perms = self.edUser.getPermissions(field_type.permissions)
            if 'w' in perms or 'r' in perms and \
                    not (self.isNew and field_type.omitForNew):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder
    allowedFields = qUtils.CachedAttribute(getAllowedFields, 'allowedFields')

    def getAllowedIndexFields(self, obj=None):
        if obj is None:
            obj = self.object
        # assume obj.type=='stream':
        stream = obj
        item_fields = stream.allStreamFields
        itemFieldsOrder = []
        if self.edUser.checkPermission('x', stream.permissions):
            for field_name in ['id']+stream.itemFieldsOrder+\
                    getattr(stream, 'joinFields', {}).keys():
                field_type = item_fields[field_name]
                if self.edUser.checkPermission('r',
                                               field_type.indexPermissions):
                    itemFieldsOrder.append(field_name)
        return itemFieldsOrder
    allowedIndexFields = qUtils.CachedAttribute(getAllowedIndexFields,
                                                'allowedIndexFields')

    def checkIfStreamUpdatable(self, obj=None):
        if obj is None:
            obj = self.object
            allowedIndexFields = self.allowedIndexFields
        else:
            allowedIndexFields = self.getAllowedIndexFields(obj)
        # assume obj.type=='stream':
        stream = obj
        if self.edUser.checkPermission('w', stream.permissions):
            item_fields = stream.allStreamFields
            for field_name in allowedIndexFields:
                field_type = item_fields[field_name]
                if self.edUser.checkPermission('w',
                                               field_type.indexPermissions):
                    return 1
        return 0
    isStreamUpdatable = qUtils.CachedAttribute(checkIfStreamUpdatable,
                                               'isStreamUpdatable')

    def checkIfStreamUnbindable(self, obj=None):
        if obj is None:
            obj = self.object
        return hasattr(obj, 'joinField') and \
                self.edUser.checkPermission('w',
                        brick.allItemFields[brick.joinField].indexPermissions)
    isStreamUnbindable = qUtils.CachedAttribute(checkIfStreamUnbindable,
                                                'isStreamUnbindable')

    def checkIfStreamCreatable(self, obj=None):
        if obj is None:
            obj = self.object
        return self.edUser.checkPermission('c', obj.permissions)
    isStreamCreatable= qUtils.CachedAttribute(checkIfStreamCreatable,
                                              'isStreamCreatable')

    def checkIfStreamDeletable(self, obj=None):
        if obj is None:
            obj = self.object
        return self.edUser.checkPermission('d', obj.permissions)
    isStreamDeletable= qUtils.CachedAttribute(checkIfStreamDeletable,
                                              'isStreamDeletable')

    def getBindingIndexFields(self, obj=None):
        if obj is None:
            obj = self.object
        # assume self.object.type=='stream':
        stream = obj
        item_fields = stream.allItemFields
        itemFieldsOrder = []
        for field_name in ['id']+stream.itemFieldsOrder:
            field_type = item_fields[field_name]
            if field_type.showInBinding and \
                    self.edUser.checkPermission('r',
                                                field_type.indexPermissions):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder
    bindingIndexFields = qUtils.CachedAttribute(getBindingIndexFields)

    def showField(self, name):
        '''Return representation of field in editor interface'''
        obj = self.object
        field_type = obj.stream.allItemFields[name]
        stream_perms = self.edUser.getPermissions(obj.stream.permissions)
        perms = self.edUser.getPermissions(field_type.permissions)
        if 'w' in stream_perms and 'w' in perms:
            template_type = 'edit'
        elif 'r' in perms:
            template_type = 'view'
        else:
            return ''
        return field_type.show(self, name, template_type,
                               self.getFieldTemplate,
                               self.fieldGlobalNamespace)

    def showFieldInIndex(self, item, name, allow_edit=1):
        '''Return representation of field in stream'''
        obj = item.stream
        field_type = obj.allStreamFields[name]
        stream_perms = self.edUser.getPermissions(obj.permissions)
        perms = self.edUser.getPermissions(field_type.indexPermissions)
        if allow_edit and 'w' in stream_perms and 'w' in perms:
            template_type = 'edit'
        elif 'r' in perms:
            template_type = 'view'
        else:
            return ''
        template_type = 'index-' + template_type
        return field_type.show(item, name, template_type,
                               self.getFieldTemplate,
                               self.fieldGlobalNamespace)

    def getPermissions(self, obj=None):
        if obj is None:
            obj = self.object
        return self.edUser.getPermissions(obj.permissions)

    getFieldPermissions = getPermissions


class EditBase:
    '''Base class for editor interface'''
    proxyClass = MakedEditObject # class of object wrapper
    streamLoaderClass = qPath.PagedStreamLoader
    
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

    def getFieldTemplate(self):
        return qWebUtils.TemplateGetter(self.fieldTemplateDirs,
                                        self.site.templateCharset)
    getFieldTemplate = qUtils.CachedAttribute(getFieldTemplate)

    def __init__(self, site):
        self.site = site
        self.parsePath = qPath.PathParser(site,
                                          item_extensions=self.item_extensions,
                                          index_file=self.index_file)

    def allowedFields(self, stream, user):
        itemFieldsOrder = []
        item_fields = stream.allItemFields
        for field_name in stream.itemFieldsOrder:
            field_type = item_fields[field_name]
            if user.checkPermission('w', field_type.permissions):
                itemFieldsOrder.append(field_name)
        return itemFieldsOrder

    def allowedStreamFields(self, stream, user):
        itemFieldsOrder = []
        item_fields = stream.allStreamFields
        for field_name in stream.itemFieldsOrder+\
                getattr(stream, 'joinFields', {}).keys():
            field_type = item_fields[field_name]
            if user.checkPermission('w', field_type.indexPermissions):
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

    def prepareObject(self, obj, user, isNew=0):
        return self.proxyClass(obj,
                               template_getter=self.getTemplate,
                               field_template_getter=self.getFieldTemplate,
                               global_namespace=self.globalNamespace,
                               edUser=user, edPrefix=self.prefix, isNew=isNew)

    def showBrick(self, request, response, obj, user, isNew=0, **kwargs):
        obj = self.prepareObject(obj, user, isNew)
        response.setContentType('text/html',
                                charset=self.getClientCharset(request))
        response.write(obj.template(obj.type, **kwargs))

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
        item = stream.createNewItem(stream.itemIDField.getDefault())
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
        if stream.itemIDField.omitForNew:
            item_id = None
        else:
            try:
                item_id = stream.itemIDField.convertFromForm(form, 'id')
            except stream.itemIDField.InvalidFieldContent, exc:
                errors['id'] = exc.message
                item_id = stream.itemIDField.getDefault()
        item = stream.createNewItem(item_id)
        if not (stream.itemIDField.omitForNew or errors) and item.exists()==1:
            raise self.ClientError(403, self.existing_id_error)
        errors.update(item.initFieldsFromForm(
                        form, names=self.allowedFields(stream, user)))
        if errors:
            for field_name, message in errors.items():
                logger.warning('Invalid content of field %r: %s',
                               field_name, message)
            return self.showBrick(request, response, item, user,
                                  isNew=1, fieldErrors=errors)
        else:
            item.store()
            if item.existsInStream():
                raise self.SeeOther(self.prefix+item.path())
            else:
                raise self.SeeOther(self.prefix+item.stream.path())

    def do_updateItem(self, request, response, form, objs, user):
        '''Update existing item with form data.  The path corresponds to item
        being updated.'''
        item = objs[-1]
        if item.type!='item':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if not user.checkPermission('w', item.stream.permissions):
            raise self.ClientError(403, self.edit_denied_error)
        errors = item.initFieldsFromForm(
                    form, names=self.allowedFields(item.stream, user))
        if errors:
            for field_name, message in errors.items():
                logger.warning('Invalid content of field %r: %s',
                               field_name, message)
            return self.showBrick(request, response, item, user,
                                  fieldErrors=errors)
        else:
            fields_to_store = []
            for field_name, field_type in item.stream.allItemFields.items():
                if field_name!='id' and \
                        user.checkPermission('w', field_type.permissions):
                    fields_to_store.append(field_name)
            item.store(fields_to_store)
            if item.existsInStream():
                raise self.SeeOther(self.prefix+item.path())
            else:
                raise self.SeeOther(self.prefix+item.stream.path())

    def deleteItems(self, stream, form, user):
        '''Method to delete items from stream.  List of item IDs is taken from
        "qps-select" form field.'''
        if not user.checkPermission('d', stream.permissions):
            raise self.ClientError(403, self.delete_denied_error)
        item_ids = map(stream.itemIDField.convertFromString,
                       form.getlist('qps-select'))
        if item_ids:
            try:
                stream.deleteItems(item_ids)
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

    def updateStream(self, stream, form, user):
        '''Method to update several items of stream at once.  Only changed
        fields are updated.  Names for fields are rewriten (in sense of
        field_type.convertFromForm()) from "name" to "qps-old:%s:%s" %
        (item.id, name) and "qps-new:%s:%s" % (item.id, name).'''
        if not user.checkPermission('w', stream.permissions):
            raise self.ClientError(403, self.edit_denied_error)
        updatable_fields = self.allowedStreamFields(stream, user)
        item_fields = stream.allStreamFields
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
                item_id = stream.itemIDField.convertFromString(item_id_str)
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
                                'Error in updateStream for field %s: %s',
                                field_name, exc.message)
                if changed_fields:
                    item.store(changed_fields)

    def do_updateStream(self, request, response, form, objs, user):
        '''Update several items of stream.  The path corresponds to stream, of
        which items are updated.'''
        stream = objs[-1]
        if stream.type!='stream':
            return self.cmd_invalidCommand(request, response, form, objs, user)
        self.updateStream(stream, form, user)
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
        field_type = stream.allItemFields[field_name]
        if not (user.checkPermission('w', stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        binding_to_item = getattr(stream, stream.virtual.paramName)
        item_ids = map(stream.itemIDField.convertFromString,
                       form.getlist('qps-select'))
        for item_id in item_ids:
            item = stream.retrieveItem(item_id)
            values = getattr(item, field_name)
            values = [value for value in values
                      if value!=binding_to_item]
            setattr(item, field_name, values)
            item.store([field_name])
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
            isBound = lambda item: binding_to_item in getattr(item, field_name)
            bound_stream = bound
        elif bound.type=='item':
            field_name = form.getfirst('field')
            binding_to_item = bound
            isBound = lambda item: item in getattr(binding_to_item, field_name)
            bound_stream = bound.stream
        else:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if field_name is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_type = bound_stream.allItemFields[field_name]
        if not (user.checkPermission('w', bound_stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        obj = self.prepareObject(template_stream, user)
        response.setContentType('text/html',
                                charset=self.getClientCharset(request))
        response.write(obj.template('binding', item=binding_to_item,
                                    fieldName=field_name,
                                    bound=bound, boundPath=bound_path,
                                    isBound=isBound))

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
            isBound = lambda item: binding_to_item in getattr(item, field_name)
            bound_stream = bound
        elif bound.type=='item':
            field_name = form.getfirst('field')
            binding_to_item = bound
            isBound = lambda item: item in getattr(binding_to_item, field_name)
            bound_stream = bound.stream
        else:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        if field_name is None:
            return self.cmd_invalidCommand(request, response, form, objs, user)
        field_type = bound_stream.allItemFields[field_name]
        if not (user.checkPermission('w', bound_stream.permissions) and \
                user.checkPermission('w', field_type.permissions)):
            raise self.ClientError(403, self.edit_denied_error)
        old_ids = map(template_stream.itemIDField.convertFromString,
                      form.getlist('qps-old'))
        new_ids = map(template_stream.itemIDField.convertFromString,
                      form.getlist('qps-new'))
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
        else:  # reverse binding
            values = list(getattr(bound, field_name))
            for item_id in old_ids:
                if item_id not in new_ids:
                    values = [value for value in values if value.id!=item_id]
            for item_id in new_ids:
                if item_id not in old_ids:
                    item = template_stream.retrieveItem(item_id)
                    values.append(item)
            if values!=getattr(bound, field_name):
                setattr(bound, field_name, values)
                bound.store()
        raise self.SeeOther(
            '%s%s?qps-action%%3AshowBinding=1&bound=%s&field=%s&page=%s' % \
                            (self.prefix, template_stream.path(), bound.path(),
                             field_name, template_stream.page))

class Edit(EditBase, qCommands.Publisher, qCommands.FieldNameCommandDispatcher,
           qSecurity.BasicAuthHandler):
    pass

# vim: ts=8 sts=4 sw=4 ai et
