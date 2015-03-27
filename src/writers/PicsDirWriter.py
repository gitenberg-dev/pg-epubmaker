#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

PicsDirWriter.py

Copyright 2012 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Copies pics into local directory. Needed for HTML and Xetex.

"""

from __future__ import with_statement

import os
import copy

from lxml import etree
from pkg_resources import resource_string # pylint: disable=E0611

import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import xpath
from epubmaker.lib.Logger import info, debug, error, exception

from epubmaker import writers


class Writer (writers.BaseWriter):
    """ Writes Pics directory. """


    # def copy_aux_files_lowlevel (self, dest_dir):
    #     """ Copy image files to dest_dir. """
        
    #     for src_uri in self.get_aux_file_list ():
    #         fn_dest = gg.make_url_relative (self.options.base_url, src_uri)
    #         fn_dest = os.path.join (dest_dir, fn_dest)
            
    #         if gg.is_same_path (src_uri, fn_dest):
    #             debug ('Not copying %s to %s: same file' % (src_uri, fn_dest))
    #             continue
    #         debug ('Copying %s to %s' % (src_uri, fn_dest))

    #         fn_dest = gg.normalize_path (fn_dest)
    #         gg.mkdir_for_filename (fn_dest)
    #         try:
    #             fp_src = urllib.urlopen (src_uri)
    #             if fp_src:
    #                 with open (fn_dest, 'wb') as fp_dest:
    #                     fp_dest.write (fp_src.read ())
    #         except IOError, what:
    #             error ('Cannot copy %s to %s: %s' % (src_uri, fn_dest, what))


    def copy_aux_files (self, dest_dir):
        """ Copy image files to dest_dir. Use image data cached in parsers. """

        for p in self.spider.parsers:
            if hasattr (p, 'resize_image'):
                src_uri = p.url
                fn_dest = gg.make_url_relative (self.options.base_url, src_uri)
                fn_dest = os.path.join (dest_dir, fn_dest)

                if gg.is_same_path (src_uri, fn_dest):
                    debug ('Not copying %s to %s: same file' % (src_uri, fn_dest))
                    continue
                debug ('Copying %s to %s' % (src_uri, fn_dest))

                fn_dest = gg.normalize_path (fn_dest)
                gg.mkdir_for_filename (fn_dest)
                try:
                    with open (fn_dest, 'wb') as fp_dest:
                        fp_dest.write (p.serialize ())
                except IOError, what:
                    error ('Cannot copy %s to %s: %s' % (src_uri, fn_dest, what))


                    
    def build (self):
        """ Build Pics file. """

        dir = self.options.outputdir

        info ("Creating Pics directory in: %s" % dir)

        self.copy_aux_files (dir)
        
        info ("Done Pics directory in: %s" % dir)



