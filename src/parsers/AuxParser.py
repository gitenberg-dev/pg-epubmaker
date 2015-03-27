#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

AuxParser.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Open an url and return raw data.

"""


from epubmaker.parsers import ParserBase

mediatypes = ('*/*', )

class Parser (ParserBase):
    """ Parse an auxiliary file. """

    def __init__ (self):
        ParserBase.__init__ (self)
        self.data = None


    def parse (self):
        """ Parse the file. """
        self.data = self.bytes_content ()


    def serialize (self):
        """ Serialize file to string. """
        return self.data
