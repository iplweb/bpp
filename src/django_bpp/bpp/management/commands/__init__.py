# -*- encoding: utf-8 -*-

__author__ = 'dotz'

import os


def files_or_directory(args, extension=".xlsx"):
    pliki = args
    if os.path.isdir(args[0]):
        pliki = [
            os.path.join(args[0], x) for x in os.listdir(args[0]) if x.endswith(extension)]

    for plik in pliki:
        yield plik
