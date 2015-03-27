#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""
TxtPackager.py

Copyright 2010 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Package a Txt file for PG.

"""

from epubmaker.packagers import OneFileZipPackager

TYPE = 'ww'
FORMATS = 'txt.us-ascii txt.iso-8859-1 txt.utf-8'.split ()

class Packager (OneFileZipPackager):
    """ WW packager for plain text files. """
    pass

