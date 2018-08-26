#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

WriterFactory.py

Copyright 2009-14 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Writer factory. Dynamically loads writers from directories.

"""

from __future__ import with_statement

import os.path

from pkg_resources import resource_isdir, resource_listdir # pylint: disable=E0611

from epubmaker.lib.Logger import debug

writers = {}

def __load_writers_from (package_name):
    """ See what types we can write. """

    try:
        for fn in resource_listdir (package_name, ''):
            modulename, ext = os.path.splitext (fn)
            if ext == '.py':
                if modulename.endswith ('Writer'):
                    type_ = modulename.lower ().replace ('writer', '')
                    debug ("Loading writer type %s from module %s" % (type_, modulename))
                    module = __import__ (package_name + '.' + modulename, fromlist = [modulename])
                    writers[type_] = module

    except ImportError:
        pass


def load_writers ():
    """ See what types we can write. """

    __load_writers_from ('epubmaker.writers')
    __load_writers_from ('epubmaker.writers.ibiblio')

    return writers.keys ()


def unload_writers ():
    """ Unload writer modules. """
    for k in writers.keys ():
        del writers[k]


def create (type_):
    """ Load writer module for type. """

    try:
        return writers[type_].Writer ()
    except KeyError:
        raise KeyError ('No writer for type %s' % type_)


