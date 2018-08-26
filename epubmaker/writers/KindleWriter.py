#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

KindleWriter.py

Copyright 2009-2012 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

"""

import re
import os
import subprocess

from epubmaker.lib.Logger import info, debug, warn, error
from epubmaker.lib.GutenbergGlobals import SkipOutputFormat
from epubmaker.writers import EpubWriter


class Writer (EpubWriter.Writer):
    """ Class for writing kindle files. """


    def parse (self, options):
        """ Standard parse. """
        self.setup (options)


    def build (self):
        """ Build kindle file. """

        # Build a special temporary epub file for kindlegen input.
        # This file is a valid epub but contains strongly simplified HTML.
        
        # Much unnecessary juggling of files here because
        # brain-dead kindlegen doesn't understand unix pipes
        # and can only output in current directory.
        # Furthermore we must not conflict with the filenames
        # of the other generated epub files.

        kindle_filename = self.options.outputfile
        epub_filename   = self.options.epub_filename

        # tmp_epub_filename = os.path.splitext (kindle_filename)[0] + '-kindlegen.epub'
        # 
        # debug ("Creating temp Epub file: %s" % os.path.join (
        #     self.options.outputdir, tmp_epub_filename))
        # 
        # # call EpubWriter to build temporary epub file
        # self.options.outputfile = tmp_epub_filename
        # EpubWriter.Writer.build (self)
        # self.options.outputfile = kindle_filename
        
        info ("Creating Kindle file: %s" % os.path.join (
            self.options.outputdir, kindle_filename))
        info ("            ... from: %s" % os.path.join (
            self.options.outputdir, epub_filename))

        try:
            cwd = os.getcwd ()
            os.chdir (self.options.outputdir)

            kindlegen = subprocess.Popen (
                [options.config.MOBIGEN, '-o', os.path.basename (kindle_filename), epub_filename],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        except OSError, what:
            os.chdir (cwd)
            error ("KindleWriter: %s %s" % (options.config.MOBIGEN, what))
            raise SkipOutputFormat
        
        (stdout, stderr) = kindlegen.communicate ('')

        # try:
        #     # if self.options.verbose < 2:
        #     #     os.remove (tmp_epub_filename)
        #     os.remove (kindle_filename)
        # except OSError:
        #     pass
        #
        # tmp_mobi_filename = os.path.splitext (tmp_epub_filename)[0] + '.mobi'
        # os.rename (tmp_mobi_filename, kindle_filename)

        os.chdir (cwd)

        regex = re.compile ('^(\w+)\(prcgen\):')

        if kindlegen.returncode > 0:
            # pylint: disable=E1103
            info (stderr.rstrip ())
            msg = stdout.rstrip ()
            for line in msg.splitlines ():
                match = regex.match (line)
                if match:
                    sline = regex.sub ("", line)
                    g = match.group (1).lower ()
                    if g == 'info':
                        if sline == 'MOBI File generated with WARNINGS!':
                            # we knew that already
                            continue
                        # info ("kindlegen: %s" % sline)
                    elif g == 'warning':
                        if sline.startswith ('Cover is too small'):
                            continue
                        if sline == 'Cover not specified':
                            continue
                        warn ("kindlegen: %s" % sline)
                    elif g == 'error':
                        error ("kindlegen: %s" % sline)
                    else:
                        error (line)

        info ("Done Kindle file: %s" % os.path.join (
            self.options.outputdir, kindle_filename))

