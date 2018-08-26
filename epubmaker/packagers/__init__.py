#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

Packager package

Copyright 2009-2010 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Base class for Packager modules.

"""

from __future__ import with_statement

import os.path
import gzip
import zipfile

from pkg_resources import resource_listdir  # pylint: disable=E0611

from epubmaker.lib.Logger import debug, info, warn, error
import epubmaker.lib.GutenbergGlobals as gg

GZIP_EXTENSION = '.gzip'

class BasePackager (object):
    """
    Base class for Packagers.

    """

    def __init__ (self):
        self.options = None
        self.path_name_ext = None
        self.path = None
        self.name = None
        self.ext = None


    def setup (self, options):
        """ Setup """
        
        self.options = options
        self.path_name_ext = os.path.join (self.options.outputdir, self.options.outputfile)
        self.path, name = os.path.split (self.path_name_ext)
        self.name, self.ext = os.path.splitext (name)


    def package (self, aux_file_list = []):
        """ Package files. """
        pass


class OneFileGzipPackager (BasePackager):
    """ Gzips one file. """

    def package (self, aux_file_list = []):
        filename = self.path_name_ext
        gzfilename = filename + GZIP_EXTENSION

        try:
            info ('Creating Gzip file: %s' % gzfilename)
            with open (filename, 'r') as fp:
                fpgz = gzip.open (gzfilename, 'w')
                info ('  Adding file: %s' % filename)
                fpgz.write (fp.read ())
                fpgz.close ()
                info ('Done Zip file: %s' % gzfilename)
        except IOError, what:
            error (what)
            

class OneFileZipPackager (BasePackager):
    """ Packages one file in zip of the same name. """

    def package (self, aux_file_list = []):
        filename = self.path_name_ext
        zipfilename = os.path.join (self.path, self.name) + '.zip'
        memberfilename = self.name + self.ext

        info ('Creating Zip file: %s' % zipfilename)

        try:
            os.stat (filename)
        except OSError:
            # warn ('Packager: Cannot find file %s', filename)
            return
        
        zip_ = zipfile.ZipFile (zipfilename, 'w', zipfile.ZIP_DEFLATED)
        info ('  Adding file: %s as %s' % (filename, memberfilename))
        zip_.write (filename, memberfilename)
        zip_.close ()

        info ('Done Zip file: %s' % zipfilename)


class HTMLishPackager (BasePackager):
    """ Package a file with images. """

    def package (self, aux_file_list = []):
        
        filename = self.options.outputfile
        zipfilename = os.path.join (self.path, self.name) + '.zip'
        memberfilename = os.path.join (self.name, self.name) + self.ext

        info ('Creating Zip file: %s' % zipfilename)

        zip_ = zipfile.ZipFile (zipfilename, 'w', zipfile.ZIP_DEFLATED)
        info ('  Adding file: %s as %s' % (filename, memberfilename))
        zip_.write (filename, memberfilename)

        # now images
        for url in aux_file_list:
            rel_url = gg.make_url_relative (self.options.base_url, url)
            filename = os.path.join (self.path, rel_url)
            memberfilename = os.path.join (self.name, rel_url)
            info ('  Adding file: %s as %s' % (filename, memberfilename))
            zip_.write (filename, memberfilename)
        
        zip_.close ()

        info ('Done Zip file: %s' % zipfilename)

    
class PackagerFactory (object):
    """ Implements Factory pattern for packagers. """

    packagers = {}

    def __init__ (self, type_):
        self.type = type_
        

    def load (self):
        """ Load the packagers in the packagers directory. """

        for fn in resource_listdir ('epubmaker.packagers', ''):
            modulename, ext = os.path.splitext (fn)
            if ext == '.py':
                if modulename.endswith ('Packager'):
                    module = __import__ ('epubmaker.packagers.' + modulename,
                                         fromlist = [modulename])
                    if self.type == module.TYPE:
                        debug ("Loading packager type: %s from module: %s for formats: %s" % (
                            self.type, modulename, ', '.join (module.FORMATS)))
                        for format_ in module.FORMATS:
                            self.packagers[format_] = module

        return self.packagers.keys ()


    def unload (self):
        """ Unload packager modules. """

        for k in self.packagers.keys ():
            del self.packagers[k]


    def create (self, format_):
        """ Create a packager for format. """

        try:
            return self.packagers[format_].Packager ()
        except KeyError:
            raise KeyError ('No packager for type %s' % format_)
    
