from __future__ import print_function
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import io
import codecs
import os
import sys

import commonmark

here = os.path.abspath(os.path.dirname(__file__))

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.rst')

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

setup(
    name='pycommonmark',
    version=commonmark.__version__,
    url='http://github.com/bpabel/pycommonmark/',
    license='MIT',
    author='Brendan Abel',
    tests_require=['pytest'],
    install_requires=[
        'html5charref',
    ],
    cmdclass={'test': PyTest},
    author_email='007brendan@gmail.com',
    description='CommonMark-compliant Markdown parser for python.',
    long_description=long_description,
    packages=['commonmark'],
    package_dir={'commonmark': 'commonmark'},
    include_package_data=True,
    platforms='any',
    test_suite='commonmark.tests.test_commonmark',
    classifiers=[
        'Programming Language :: Python',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: CGI Tools/Libraries',
        'Topic :: Text Processing :: Markup',
        'Topic :: Text Processing :: Markup :: HTML',
        ],
    extras_require={
        'testing': ['pytest'],
    }
)
