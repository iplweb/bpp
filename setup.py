#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()
    
reqs = lambda fn: list([x.strip() for x in open(fn).readlines() if x.strip() and not x.startswith("#")])      

requirements = reqs("requirements/requirements.txt")

test_requirements = reqs("requirements/requirements_dev.txt") + requirements

setup(
    name='django_bpp',
    version='0.10.96',
    description="System informatyczny do zarządzania bibliografią publikacji pracowników naukowych",
    long_description=readme + '\n\n' + history,
    author="Michał Pasternak",
    author_email='michal.dtz@gmail.com',
    url='https://github.com/mpasternak/django_bpp',
    packages=find_packages("src"),
    package_dir={
        '': 'src'
        },
    package_data={'django_bpp': ['src/staticroot/*']},
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='django_bpp',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Polish',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: JavaScript',
        'Programming Language :: PL/SQL',        
    ],
# Someday: 
#    test_suite=[
#        'functional_tests', 
#        'bpp.tests', 
#        'egeria.tests', 
#        'eksport_pbn.tests', 
#        'integrator2.tests'
#    ],
    tests_require=test_requirements,
    scripts=["src/bin/bpp-manage.py"],
    python_requires=">=2.7,<3"
)
