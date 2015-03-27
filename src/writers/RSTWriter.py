#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""
RSTWriter.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Build an RST file. This is just the master RST with the PG license mixed in.

"""

from __future__ import with_statement

import os

from epubmaker.lib.Logger import debug, info, error
from epubmaker import ParserFactory
from epubmaker import writers

class Writer (writers.BaseWriter):
    """ Class to write a reStructuredText. """

    def build (self):
        """ Build RST file. """

        filename = os.path.join (self.options.outputdir, self.options.outputfile)

        info ("Creating RST file: %s" % filename)

        parser = ParserFactory.ParserFactory.create (self.options.candidate.filename,
                                                     self.options.candidate.mediatype)
        parser.options = self.options

        if not hasattr (parser, 'rst2nroff'):
            error ('RSTWriter can only work on a RSTParser.')
            return
        
        data = parser.preprocess ('utf-8').encode ('utf-8')

        self.write_with_crlf (filename, data)
        
        info ("Done RST file: %s" % filename)


