#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.append(".")  # dla compilemessages
from distutils.cmd import Command
from distutils.command.build import build as _build

from setuptools.command.install_lib import install_lib as _install_lib

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from setuptools import setup, find_packages

with open('README.rst', encoding="utf-8") as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()
    

class compile_translations(Command):
    description = 'compile message catalogs to MO files via django compilemessages'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        curdir = os.getcwd()
        os.chdir(os.path.realpath('src'))
        from django.core.management import call_command
        call_command('compilemessages')
        os.chdir(curdir)


class build(_build):
    sub_commands = [
        ('compile_translations', None),
    ] + _build.sub_commands


class install_lib(_install_lib):
    def run(self):
        self.run_command('compile_translations')
        _install_lib.run(self)

        
def requirements(fn="requirements.txt"):
    return [l for l in open(fn).read().splitlines() if l and l[0] not in "#-"]


setup(
    name='bpp-iplweb',
    version='1.0.26-dev',
    description="System informatyczny do zarządzania bibliografią publikacji pracowników naukowych",
    long_description=readme + '\n\n' + history,
    author="Michał Pasternak",
    author_email='michal.dtz@gmail.com',
    url='http://bpp.iplweb.pl/',
    packages=find_packages("src"),
    install_requires=requirements(),
    package_dir={
        '': 'src'
        },
    include_package_data=True,
    license="MIT license",
    zip_safe=False,
    keywords='bibliografia naukowa bpp publikacje pracowników institutional repository repozytorium',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Polish',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: JavaScript',
        'Programming Language :: PL/SQL',        
    ],
    scripts=["src/bin/bpp-manage.py"],
    python_requires=">=3.6,<4",
    cmdclass={
        'build': build,
        'install_lib': install_lib,
        'compile_translations': compile_translations,
    }
)
