#!/usr/bin/env python

import os
import sys
from distutils.cmd import Command
from distutils.command.build import build as _build

from django.core.management import call_command
from setuptools import find_packages, setup
from setuptools.command.install_lib import install_lib as _install_lib

sys.path.append(".")  # dla compilemessages

with open("README.rst", encoding="utf-8") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()


class compile_translations(Command):
    description = "compile message catalogs to MO files via django compilemessages"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        curdir = os.getcwd()
        os.chdir(os.path.realpath("src"))
        call_command("compilemessages")
        os.chdir(curdir)


class build(_build):
    sub_commands = [
        ("compile_translations", None),
    ] + _build.sub_commands


class install_lib(_install_lib):
    def run(self):
        self.run_command("compile_translations")
        _install_lib.run(self)


def requirements(fn="requirements.txt"):
    for elem in [
        line.replace("\\", "").strip()
        for line in open(fn).read().splitlines()
        if line and line.find("==") > 0 and not line.strip().startswith("#")
    ]:
        if elem.find("#egg=") >= 0:
            raise Exception("To nie zadziala: " + elem)
        yield elem


setup(
    name="bpp-iplweb",
    version="202508.1206",
    description="System informatyczny do zarządzania bibliografią publikacji pracowników naukowych",
    long_description=readme,
    long_description_content_type="text/x-rst",
    author="Michał Pasternak",
    author_email="michal.dtz@gmail.com",
    url="http://bpp.iplweb.pl/",
    packages=find_packages("src"),
    install_requires=list(requirements()),
    package_dir={"": "src"},
    include_package_data=True,
    license="MIT license",
    zip_safe=False,
    keywords="bibliografia naukowa bpp publikacje pracowników institutional repository repozytorium",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Polish",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: JavaScript",
        "Programming Language :: PL/SQL",
    ],
    scripts=["src/bin/bpp-manage.py"],
    python_requires=">=3.6,<4",
    # cmdclass={
    #     "build": build,
    #     "install_lib": install_lib,
    #     "compile_translations": compile_translations,
    # },
)
