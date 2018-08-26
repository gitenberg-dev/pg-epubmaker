#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

Writer package

Copyright 2009-2010 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Base classes for *Writer modules. (EpubWriter, PluckerWriter, ...)

"""

from __future__ import with_statement

from functools import partial
import os.path
import urllib

from lxml import etree
from lxml.builder import ElementMaker

from epubmaker.lib.Logger import debug, error
import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib import MediaTypes

from epubmaker import ParserFactory
from epubmaker import Spider
from epubmaker.Version import VERSION, GENERATOR


class BaseWriter (object):
    """
    Base class for EpubWriter, PluckerWriter, ... 

    also used as /dev/null writer for debugging

    """

    def __init__ (self):
        self.options = None
        self.spider = None


    def setup (self, options):
        """ override this in a real writer

        put computationally cheap setup stuff in here,
        
        """

        if not options.include_mediatypes:
            options.include_mediatypes = (
                MediaTypes.TEXT_MEDIATYPES |
                MediaTypes.AUX_MEDIATYPES |
                MediaTypes.IMAGE_MEDIATYPES
                )

        self.options = options


    def parse (self, options):
        """ Standard parse. """
        self.setup (options)

        if self.spider is None:
            self.spider = Spider.Spider ()

        self.spider.parse (options.candidate.filename, 
                           options.candidate.mediatype,
                           options)

        options.candidate.filename = self.spider.redirect (options.candidate.filename)
        options.base_url = options.candidate.filename


    def build (self):
        """ override this in a real writer """
        pass


    @staticmethod
    def write_with_crlf (filename, data):
        # \r\n is PG standard
        data = '\r\n'.join (data.splitlines ()) + '\r\n'
        
        # open binary so windows doesn't add another \r
        with open (filename, 'wb') as fp:
            fp.write (data)
            

    def validate (self): # pylint: disable=R0201
        """ Validate the output with some (external) tool.

        Override this in a real writer.

        """
        return 0


    def sync (self):
        """  Override this if you need to sync before program exit. """
        pass


    def make_links_relative (self, xhtml, base_url):
        """ Make absolute links in xhtml relative to base_url. """

        debug ("Making links relative to: %s" % base_url)
        xhtml.rewrite_links (partial (gg.make_url_relative, base_url))


    def get_aux_file_list (self):
        """ Iterate over image files. Return absolute urls. """

        for p in self.spider.parsers:
            if hasattr (p, 'resize_image'):
                yield p.url


em = ElementMaker (namespace = str (gg.NS.xhtml),
                   nsmap = { None: str (gg.NS.xhtml) })


class HTMLishWriter (BaseWriter):
    """ Base class for writers with HTMLish contents. """

    @staticmethod
    def add_class (elem, class_):
        """ Add a class to html element. """

        classes = elem.get ('class', '').split ()
        classes.append (class_)
        elem.set ('class', ' '.join (classes))


    @staticmethod
    def add_meta (xhtml, name, content):
        """ Add a meta tag. """
        
        for head in gg.xpath (xhtml, '//xhtml:head'):
            meta = em.meta (name = name, content = content)
            meta.tail = '\n'
            head.append (meta)
        

    @staticmethod
    def add_meta_generator (xhtml):
        """ Add our piss mark. """

        HTMLishWriter.add_meta (xhtml, 'generator', GENERATOR % VERSION)


    @staticmethod
    def add_internal_css (xhtml, css_as_string):
        """ Add internal stylesheet to html. """
        
        if css_as_string and xhtml is not None:
            css_as_string = '\n' + css_as_string.strip (' \n') + '\n'
            for head in gg.xpath (xhtml, '//xhtml:head'):
                style = em.style (css_as_string, type = 'text/css')
                style.tail = '\n'
                head.append (style)


    def add_external_css (self, xhtml, css_as_string, url):
        """ Add external stylesheet to html. """
        
        if css_as_string:
            p = ParserFactory.ParserFactory.get ('text/css')
            p.parse_string (css_as_string)
            p.url = url
            self.spider.parsers.append (p)
            
        if xhtml is not None:
            for head in gg.xpath (xhtml, '//xhtml:head'):
                link = em.link (href = url, rel = 'stylesheet', type = 'text/css')
                link.tail = '\n'
                head.append (link)





    

