#!/usr/bin/env python

from distutils.core import setup
import qps

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
      packages=['qps', 'qps.qDB', 'qps.qBricks'])
