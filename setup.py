#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.rst', encoding="utf-8") as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()
    
def parse_reqs(fn):
    for line in open(fn).readlines():
        line = line.strip()
        if line:

            if line.startswith("#") or line.startswith("-r"):
                continue

            if line.startswith("git+https"):
                _ignore, line = line.split("#egg=", 2)

            yield line


requirements = list(parse_reqs("requirements.txt"))

test_requirements = list(parse_reqs("requirements_dev.txt")) + requirements

setup(
    name='django-bpp',
    version='0.11.80',
    description="System informatyczny do zarządzania bibliografią publikacji pracowników naukowych",
    long_description=readme + '\n\n' + history,
    author="Michał Pasternak",
    author_email='michal.dtz@gmail.com',
    url='https://github.com/mpasternak/django-bpp',
    packages=find_packages("src"),
    package_dir={
        '': 'src'
        },
    # package_data={'django_bpp': ['src/staticroot/*']},
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
        'Programming Language :: Python :: 3.6',
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
    python_requires=">=3.6,<4"
)
