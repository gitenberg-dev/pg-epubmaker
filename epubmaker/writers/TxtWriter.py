#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""
TxtWriter.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Build an UTF-8-encoded PG plain text file. This is just the plain text
version recoded into UTF-8.

"""

from __future__ import with_statement

import os
import subprocess

from epubmaker.lib.Logger import debug, info, warn, error
from epubmaker.lib.GutenbergGlobals import SkipOutputFormat

from epubmaker import ParserFactory
from epubmaker import writers

# map some not-widely-supported characters to more common ones
u2u = {
    0x2010: u'-',  # unicode HYPHEN to HYPHEN-MINUS. Many Windows fonts lack this.
    }

class Writer (writers.BaseWriter):
    """ Class to write PG plain text. """

    def groff (self, nroff, encoding = 'utf-8'):
        """ Process thru groff.

        Takes and returns unicode strings!

        """

        device = { 'utf-8': 'utf8',
                   'iso-8859-1': 'latin1',
                   'us-ascii': 'ascii' }[encoding]
        
        nroff = nroff.encode (encoding)
        nrofffilename = os.path.join (
            self.options.outputdir,
            os.path.splitext (self.options.outputfile)[0] + '.nroff')

        # write nroff file for debugging
        if options.verbose >= 2:
            with open (nrofffilename, 'w') as fp:
                fp.write (nroff)
        else:
            try:
                # remove debug files from previous runs
                os.remove (nrofffilename)
            except OSError:
                pass

        # call groff
        try:
            _groff = subprocess.Popen ([options.config.GROFF, 
                                       "-t",             # preprocess with tbl
                                       "-K", device,     # input encoding
                                       "-T", device],    # output device
                                      stdin = subprocess.PIPE, 
                                      stdout = subprocess.PIPE, 
                                      stderr = subprocess.PIPE)
        except OSError:
            error ("TxtWriter: executable not found: %s" % options.config.GROFF)
            raise SkipOutputFormat

        (txt, stderr) = _groff.communicate (nroff)
        
        # pylint: disable=E1103
        for line in stderr.splitlines ():
            line = line.strip ()
            if 'error' in line:
                error ("groff: %s" % line)
            elif 'warn' in line:
                if options.verbose >= 1:
                    warn ("groff: %s" % line)

        txt = txt.decode (encoding)
        return txt.translate (u2u) # fix nroff idiosyncracies


    def build (self):
        """ Build TXT file. """

        filename = os.path.join (self.options.outputdir, self.options.outputfile)

        encoding = options.subtype.strip ('.')

        info ("Creating plain text file: %s" % filename)

        parser = ParserFactory.ParserFactory.create (self.options.candidate.filename,
                                                     self.options.candidate.mediatype)
        parser.options = self.options

        if hasattr (parser, 'rst2nroff'):
            data = self.groff (parser.rst2nroff (encoding), encoding)
        else:
            data = parser.unicode_content ()

        data = data.encode ('utf_8_sig' if encoding == 'utf-8' else encoding, 'unitame')

        self.write_with_crlf (filename, data)
            
        info ("Done plain text file: %s" % filename)


