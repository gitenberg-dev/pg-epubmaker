#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

CSSParser.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Open an url and return raw data.

"""

import re
import urlparse
import logging

import cssutils

from epubmaker.lib.Logger import debug
from epubmaker.lib.MediaTypes import mediatypes as mt

from epubmaker.parsers import ParserBase

RE_ELEMENT = re.compile (r'((?:^|\s)[a-z0-9]+)', re.I)

mediatypes = (mt.css, )

class Parser (ParserBase):
    """ Parse an external CSS file. """

    def __init__ (self):
        cssutils.log.setLog (logging.getLogger ('cssutils'))
        # logging.DEBUG is way too verbose
        cssutils.log.setLevel (max (cssutils.log.getEffectiveLevel (), logging.INFO))
        ParserBase.__init__ (self)
        self.sheet = None


    def parse (self):
        """ Parse the CSS file. """

        if self.sheet is not None:
            return
        
        parser = cssutils.CSSParser ()
        self.sheet = parser.parseUrl (self.url)

        self.mediatype = 'text/css'
        self.unpack_media_handheld (self.sheet)
        self.lowercase_selectors (self.sheet)


    def parse_string (self, s):
        """ Parse the CSS in string. """

        if self.sheet is not None:
            return
        
        parser = cssutils.CSSParser ()
        self.sheet = parser.parseString (s, encoding = 'utf-8')

        self.mediatype = 'text/css'
        self.unpack_media_handheld (self.sheet)
        self.lowercase_selectors (self.sheet)


    @staticmethod
    def iter_properties (sheet):
        """ Iterate on properties in css. """
        for rule in sheet:
            if rule.type == rule.STYLE_RULE:
                for prop in rule.style:
                    yield prop


    @staticmethod
    def unpack_media_handheld (sheet):
        """ unpack a @media handheld rule """
        for rule in sheet:
            if rule.type == rule.MEDIA_RULE:
                if rule.media.mediaText.find ('handheld') > -1:
                    debug ("Unpacking CSS @media handheld rule.")
                    rule.media.mediaText = 'all'
                    rule.insertRule (cssutils.css.CSSComment ('/* was @media handheld */'), 0)


    @staticmethod
    def lowercase_selectors (sheet):
        """ make selectors lowercase to match xhtml tags """
        for rule in sheet:
            if rule.type == rule.STYLE_RULE:
                for sel in rule.selectorList:
                    sel.selectorText = RE_ELEMENT.sub (lambda m: m.group(1).lower (),
                                                       sel.selectorText)


    def rewrite_links (self, f):
        """ Rewrite all links using the function f. """
        cssutils.replaceUrls (self.sheet, f)


    def drop_floats (self):
        """ Drop all floats in stylesheet.

        """

        for prop in self.iter_properties (self.sheet):
            if prop and prop.name == 'float': # test for existence because we remove
                prop.parent.removeProperty ('float')
                prop.parent.removeProperty ('width')
                prop.parent.removeProperty ('height')
            elif prop and prop.name in ('position', 'left', 'right', 'top', 'bottom'):
                prop.parent.removeProperty (prop.name)
                
        for prop in self.iter_properties (self.sheet):
            #print prop.name
            #print prop.value
            if prop and prop.value.endswith ('px'): # test for existence because we remove
                prop.parent.removeProperty (prop.name)


    def get_image_urls (self):
        """ Return the urls of all images in document.

        Images are graphic files. The user may choose if he wants
        images included or not.

        """

        images = []
        
        for prop in self.iter_properties (self.sheet):
            if (prop.value.cssValueType == prop.value.CSS_PRIMITIVE_VALUE and
                prop.value.primitiveType == prop.value.CSS_URI):
                url = urlparse.urljoin (self.url, prop.value.cssText)
                images.append (url)
            
        return  images


    def get_aux_urls (self):
        """ Return the urls of all auxiliary files in document.

        Auxiliary files are non-document files you need to correctly
        display the document file, eg. CSS files.

        """

        aux = []
        
        for rule in self.sheet:
            if rule.type == rule.IMPORT_RULE:
                aux.append (urlparse.urljoin (self.url, rule.href))

        return  aux


    def serialize (self):
        """ Serialize CSS. """

        return self.sheet.cssText
