#!/usr/bin/env python

from distutils.core import setup
import qps

setup(name='QPS',
      version=qps.__version__,
      description='Q Publishing System (QPS) is a framework for custom '\
                  'Content Management Systems',
      url='http://ppa.sf.net/',
      license='Python-like',
      packages=['qps', 'qps.qDB', 'qps.qBricks'])
