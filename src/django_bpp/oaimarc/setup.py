# -*- encoding: utf-8 -*-

from setuptools import setup, find_packages
from os.path import join, dirname

setup(
    name='oaimarc',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'moai.format': [
            'marc=oaimarc.metadata:OAIMARC',
        ],
    },
    install_requires=[
        'moai',
    ],
)


