#!/usr/bin/env python
# $Id: setup.py,v 1.9 2004/06/28 12:06:30 ods Exp $

from distutils.core import Command, setup
from distutils.command.build import build
import os, qps


class qps_build_pydoc(Command):

    description = 'build API reference with pydoc'

    user_options = [
        ('build-dir=', 'd', 'destination directory'),
    ]

    def initialize_options(self):
        self.build_dir = None

    def finalize_options(self):
        self.set_undefined_options('build',
                                   ('build_pydoc', 'build_dir'))
        if self.distribution.packages:
            # XXX just a quick hack
            self.package = self.distribution.packages[0]
        else:
            self.package = None

    def run(self):
        if self.package:
            import pydoc
            cwd = os.getcwd()
            self.mkpath(self.build_dir)
            os.chdir(self.build_dir)
            try:
                pydoc.writedocs(os.path.join(cwd, self.package),
                                pkgpath=self.package+'.')
            except:
                if not self.dry_run:
                    os.chdir(cwd)
                    raise
            os.chdir(cwd)


class qps_build(build):

    user_options = build.user_options + [
        ('build-pydoc=', None, 'build directory for API reference'),
    ]

    sub_commands = build.sub_commands + [
        # XXX don't build by default yet
        #('build_pydoc', None),
    ]

    def initialize_options(self):
        build.initialize_options(self)
        self.build_pydoc = None

    def finalize_options(self):
        build.finalize_options(self)
        if self.build_pydoc is None:
            self.build_pydoc = os.path.join(self.build_base, 'pydoc')


def rglob(where, dir):
    result = []
    for root, dirs, files in os.walk(dir):
        if 'CVS' in dirs:
            dirs.remove('CVS')
        files = [os.path.join(root, file) for file in files
                 if not (file.startswith('.') or file.endswith('~'))]
        result.append((os.path.join(where, root), files))
    return result


setup(name='QPS',
      version=qps.__version__,
      description='Q Publishing System (QPS) is a framework for custom '\
                  'Content Management Systems',
      url='http://ppa.sf.net/#qps',
      maintainer='Denis S. Otkidach',
      maintainer_email='ods@users.sf.net',
      license='Python-like',
      classifiers = [
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Intended Audience :: Information Technology',
          'License :: OSI Approved :: Python Software Foundation License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Internet :: WWW/HTTP',
      ],
      download_url='http://prdownloads.sourceforge.net/ppa/'\
                   'QPS-%s.tar.gz?download' % qps.__version__,
      packages=['qps', 'qps.qDB', 'qps.qBricks'],
      scripts=['bin/qps_create_site'],
      data_files=rglob('share/QPS', 'themes')+\
                    rglob('share/QPS', 'protosites/tiny')+\
                    rglob('share/QPS', 'protosites/medium'),
      cmdclass={
        'build'         : qps_build,
        'build_pydoc'   : qps_build_pydoc,
      })
