# $Id: qMake.py,v 1.9 2004/07/26 08:56:17 ods Exp $

'''Defines common maker classes'''

import os, sys, logging, qUtils, qWebUtils
logger = logging.getLogger(__name__)


class AtomicWriteFile(file):

    def __init__(self, path, mode='wb', buffering=-1, charset=None):
        assert 'w' in mode
        dir = os.path.dirname(path)
        if dir and not os.path.isdir(dir):
            os.makedirs(dir)
        self._real_path = path
        self._tmp_path = '%s.new-%s~' % (path, os.getpid())
        self._charset = charset
        file.__init__(self, self._tmp_path, mode, buffering)

    def write(self, data):
        if isinstance(data, unicode):
            data = data.encode(self._charset)
        file.write(self, data)
    
    # Inherited __del__ calls file.close() and file is not renamed.  So
    # redefined close() method is like a commit.
    def close(self):
        file.close(self)
        logger.info('Writing %r', self._real_path)
        try:
            os.rename(self._tmp_path, self._real_path)
        except OSError, exc:
            import errno
            # Windows lacks atomic rename :(
            if exc.errno==errno.EEXIST:
                os.remove(self._real_path)
                os.rename(self._tmp_path, self._real_path)
            else:
                raise

    if not __debug__:
        def __del__(self):
            if not self.closed:
                file.close(self)
                os.remove(self._tmp_path)


class Writer:

    indexFile = 'index.html'
    fileClass = AtomicWriteFile
    mode = 'wb'
    buffering = -1
    charset = 'ascii'

    def __init__(self, base_dir, **params):
        self.baseDir = base_dir
        self.__dict__.update(params)

    def path(self, path):
        if path[-1:]=='/':
            path += self.indexFile
        return self.baseDir+path

    def delete(self, path):
        full_path = self.path(path)
        logger.info('Deleting %r', full_path)
        try:
            os.remove(full_path)
        except OSError:
            pass
        while 1:
            full_path = os.path.dirname(full_path)
            if full_path<=self.baseDir:
                break
            try:
                os.rmdir(full_path)
            except OSError:
                break    

    def getFP(self, path):
        full_path = self.path(path)
        if self.charset:
            return self.fileClass(full_path, self.mode, self.buffering,
                                  self.charset)
        else:
            return self.fileClass(full_path, self.mode, self.buffering)


class BaseMaker:

    def __init__(self, site, **params):
        self.site = site
        self._params = params  # useful for agregating/dispatching makers
        self.__dict__.update(params)

    def do_delete(self, brick):
        pass

    def do_make(self, brick):
        pass

    def process(self, brick):
        action = brick.makeAction()
        if action:
            getattr(self, 'do_'+action)(brick)


class Maker(BaseMaker):

    proxyClass = staticmethod(lambda x: x)
    renderHelperClass = qWebUtils.RenderHelper

    def __init__(self, site, writer=None, template_getter=None, **params):
        BaseMaker.__init__(self, site, **params)
        self.writer = site.getWriter(writer)
        self.getTemplate = site.getTemplateGetter(template_getter)
        self.globalNamespace = site.globalNamespace

    def path(self, brick):
        return brick.path()

    def do_delete(self, brick):
        path = self.path(brick)
        self.writer.delete(path)

    def getTemplateName(self, brick):
        if brick.type=='site':
            return brick.type
        if brick.type=='item':
            templateCat = brick.stream.templateCat
        else:
            templateCat = brick.templateCat
        return '.'.join([templateCat, brick.type])

    def prepareObject(self, brick):
        return self.proxyClass(brick)

    def do_make(self, brick):
        obj = self.prepareObject(brick)
        template = self.renderHelperClass(self)

        namespace = self.globalNamespace.copy()
        namespace['template'] = template
        template = self.getTemplate(self.getTemplateName(brick))

        fp = self.writer.getFP(self.path(brick))
        template.interpret(fp, namespace, {'brick': obj, '__object__': obj})
        fp.close()

       
class StreamsMaker(BaseMaker):

    def process(self, site):
        for stream in site:
            stream.make(maker_params=self._params)
            stream.clear()

class ItemsMaker(BaseMaker):

    tag = None
    skip_items = 0
    all_pages = 0
    
    def process(self, stream):
        if self.skip_items:
            return
        makers = [self.site.getMaker(desc, self._params) \
                  for desc in stream.itemMakers]
        if self.tag is not None:
            if not getattr(stream, 'tagParams', {}).has_key(self.tag):
                logger.warning('ItemsMaker is used with tag %r that is not '\
                               'defined for stream %r', self.tag, stream.id)
            stream = stream.site.retrieveStream(stream.id, tag=self.tag)
        for item in stream:
            for maker in makers:
                item.make(maker)
        if self.all_pages and stream.indexNum:
            stream = self.site.streamFactory(stream.id, tag=self.tag, page=2)
            while stream:
                for item in stream:
                    for maker in makers:
                        item.make(maker)
                stream = self.site.streamFactory(stream.id, tag=self.tag,
                                                 page=stream.page+1)


class VirtualsMaker(BaseMaker):

    skip_virtuals = 0

    def process(self, brick):
        if self.skip_virtuals:
            return
        for stream in brick.virtualStreams:
            stream.make(maker_params=self._params)
            stream.clear()


class ImagesMaker(Maker):

    def do_delete(self, item):
        from qFieldTypes import IMAGE
        from glob import glob
        for field_name, field_type in item.fields.external.iteritems():
            if isinstance(field_type, IMAGE):
                image = getattr(item, field_name)
                for old_path in glob(image.pattern+'.*'):
                    os.remove(old_path)

    def do_make(self, item):
        from qFieldTypes import IMAGE
        from glob import glob
        for field_name, field_type in item.fields.external.iteritems():
            if isinstance(field_type, IMAGE):
                image = getattr(item, field_name)
                if image:
                    fp = self.writer.getFP(image.path)
                    fp.write(open(field_type.editRoot+image.path, 'rb').read())
                    fp.close()
                else:
                    path = None
                for old_path in glob(image.pattern+'.*'):
                    if old_path!=path:
                        os.remove(old_path)


# vim: ts=8 sts=4 sw=4 ai et
