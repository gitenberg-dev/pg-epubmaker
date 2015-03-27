#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""

RSTParser.py

Copyright 2010-2012 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

"""

# FIXME:
# use docinfo instead of meta for pg header

import copy
import re
import os
import collections
import urlparse
from functools import partial

from lxml import etree
import lxml.html

import docutils.readers.standalone
from docutils import nodes, frontend, io

from pkg_resources import resource_string # pylint: disable=E0611

from epubmaker.lib.GutenbergGlobals import NS, xpath
from epubmaker.lib.Logger import info, debug, warn, error
from epubmaker.lib.MediaTypes import mediatypes as mt

from epubmaker import ParserFactory
from epubmaker.parsers import HTMLParser

from epubmaker.mydocutils import broken
from epubmaker.mydocutils import nodes as mynodes
from epubmaker.mydocutils.writers import xhtml1, epub2, xetex

from epubmaker.mydocutils.gutenberg import parsers as gutenberg_parsers
from epubmaker.mydocutils.gutenberg.writers import nroff as gutenberg_nroff

mediatypes = (mt.rst, )

RE_EMACS_CHARSET = re.compile (r'-\*-.*coding:\s*(\S+)',  re.I)

class Parser (HTMLParser.Parser):
    """ Parse a ReStructured Text 

    and convert it to different xhtml flavours.

    """

    def __init__ (self):
        HTMLParser.Parser.__init__ (self)
        self.document1 = None


    def preprocess (self, charset):
        """ Insert pg header and footer. """
        
        return self.unicode_content ()


    def to_xhtml (self, html, base_url):
        html = html.replace (u'&nbsp;', u' ')
        html = html.replace (u'&mdash;', u'—')

        outputfilename = os.path.join (options.outputdir, options.outputfile)
        debugfilename = os.path.splitext (outputfilename)[0] + '.debug.html'

        try:
            os.remove (debugfilename)
        except OSError:
            pass
        
        if options.verbose > 1:
            with open (debugfilename, 'w') as fp:
                fp.write (html.encode ('utf-8'))

        try:
            xhtml = etree.fromstring (
                html, 
                lxml.html.XHTMLParser (),
                base_url = base_url)                                           
        except etree.ParseError, what:
            error ("etree.fromstring says %s" % what)
            raise

        xhtml.make_links_absolute (base_url = base_url)

        return xhtml


    def rewrite_links (self, f):
        """ Rewrite all links using the function f. """

        doc = self.document1

        if 'coverpage' in doc.meta_block:
            coverpage = doc.meta_block['coverpage']
            coverpage[0] = f (coverpage[0])
        else:
            for field in doc.traverse (nodes.field):
                field_name, field_body = field.children
                if field_name.astext () == 'coverpage':
                    field_body[:] = nodes.paragraph ('', f (field_body.astext ()))
                    break

        for node in doc.traverse (nodes.reference):
            if 'uri' in node:
                node['uri'] = f (node['uri'])

        for node in doc.traverse (nodes.image):
            if 'uri' in node:
                node['uri'] = f (node['uri'])

        for node in doc.traverse (nodes.pending):
            # dropcap images
            if 'image' in node.details:
                node.details['image'] = f (node.details['image'])


    def iterlinks (self):
        """ Grab links and images in RST. """

        debug ("RSTParser iterlinks want_images = %d" % self.options.want_images)

        doc = self.document1

        # return coverpage even in noimages build
        if 'coverpage' in doc.meta_block:
            coverpage = doc.meta_block['coverpage']
            yield coverpage[0], {'tag': NS.xhtml.link, 
                                 'type': 'image/jpeg;type=resource', 'rel': 'coverpage'}
        else:
            for field in doc.traverse (nodes.field):
                field_name, field_body = field.children
                if field_name.astext () == 'coverpage':
                    yield field_body.astext (), {
                        'tag': NS.xhtml.link, 
                        'type': 'image/jpeg;type=resource', 
                        'rel': 'coverpage'}
                    break

        # need broken.png for no-images build
        if not self.options.want_images:
            yield (urlparse.urljoin (self.url, broken), 
                   {'tag': NS.xhtml.img, 'type': 'image/png;type=resource', 'rel': 'broken'})

        for node in doc.traverse (nodes.reference):
            if 'uri' in node:
                yield node['uri'], {'tag': NS.xhtml.a}

        if self.options.want_images:
            for node in doc.traverse (nodes.image):
                if 'uri' in node:
                    yield node['uri'], {'tag': NS.xhtml.img}

        if self.options.want_images:
            for node in doc.traverse (nodes.pending):
                # dropcap images
                if 'image' in node.details:
                    yield node.details['image'], {'tag': NS.xhtml.img}


    def get_settings (self, components, defaults):
        option_parser = frontend.OptionParser (
            components = components,
            defaults = defaults, 
            read_config_files = 1)
        return option_parser.get_default_values ()


    def pre_parse (self):
        """ Parse a RST file as link list. """

        debug ("RSTParser: Pre-parsing %s" % self.url)

        default_style = self.get_resource (
            'mydocutils.parsers', 'default_style.rst').decode ('utf-8')

        source = io.StringInput (default_style + self.unicode_content ())
        reader = docutils.readers.standalone.Reader ()
        parser = gutenberg_parsers.Parser ()

        overrides = {
            'get_resource': self.get_resource,
            'get_image_size': self.get_image_size_from_parser,
            'no_images': not self.options.want_images,
            'base_url': self.url,
            }

        doc = reader.read (
            source, parser, self.get_settings ((reader, parser), overrides))
        self.document1 = doc

        self.rewrite_links (partial (urlparse.urljoin, self.url))

        debug ("RSTParser: Done pre-parsing %s" % self.url)


    def _full_parse (self, writer, overrides):
        """ Full parse from scratch. """

        debug ("RSTParser: Full-parsing %s" % self.url)

        default_style = self.get_resource (
            'mydocutils.parsers', 'default_style.rst').decode ('utf-8')

        source = io.StringInput (default_style + self.unicode_content (), 
                                 self.url, 'unicode')
        reader = docutils.readers.standalone.Reader ()
        parser = gutenberg_parsers.Parser ()

        doc = reader.read (
            source, parser, 
            self.get_settings ((reader, parser, writer), overrides))
        self.document1 = doc

        self.rewrite_links (partial (urlparse.urljoin, self.url))

        doc.transformer.populate_from_components ((source, reader, parser, writer))
        doc.transformer.apply_transforms ()
        debug ("RSTParser: Done full-parsing %s" % self.url)

        return doc


    def _full_parse_2 (self, writer, destination, overrides):
        """ Full parser from pickled doctree. 

        Doesn't work yet. It turned out pickling a doctree is much
        harder than I thought. """

        debug ("Full-parsing %s" % self.url)

        source = io.StringInput (self.unicode_content ())
        reader = docutils.readers.standalone.Reader ()
        parser = gutenberg_parsers.Parser ()

        doc = reader.read (
            source, parser, 
            self.get_settings ((reader, parser, writer), overrides))
        self.document1 = doc

        self.rewrite_links (partial (urlparse.urljoin, self.url))

        # make it picklable
        reporter = doc.reporter #  = None
        # doc.reporter = None
        transformer = doc.transformer
        doc.settings = None
        from docutils.parsers.rst.directives.html import MetaBody

        #for metanode in doc.traverse (MetaBody.meta):
        for pending in doc.traverse (nodes.pending):
            # pending.transform = None
            # docutils' meta nodes aren't picklable because the class is nested
            # in pending['nodes']
            if 'nodes' in pending.details: 
                if isinstance (pending.details['nodes'][0], MetaBody.meta):
                    pending.details['nodes'][0].__class__ = mynodes.meta
        import cPickle as pickle
        pickled = pickle.dumps (doc)

        doc = pickle.loads (pickled)

        #doc.transformer.populate_from_components (
        #    (source, reader, parser, writer))

        doc.transformer = transformer
        doc.reporter = reporter
        doc.settings = self.get_settings ((reader, parser, writer), overrides)

        doc.transformer.apply_transforms ()

        return writer.write (doc, destination)


    def rst2nroff (self, charset = 'utf-8'):
        """ Convert RST to nroff. """

        writer = gutenberg_nroff.Writer ()
        destination = io.StringOutput (encoding = 'unicode')

        overrides = {
            'doctitle_xform': 1,
            'sectsubtitle_xform': 1,
            'footnote_references': 'superscript',
            'compact_lists': 1,
            'compact_simple': 1,
            'page_numbers': 1,
            'no_images': True,
            'get_resource': self.get_resource,
            'format': options.type,
            'encoding': charset,
            'base_url': self.url,
            }
   
        doc = self._full_parse (writer, overrides)
        return writer.write (doc, destination)


    def rst2xetex (self):
        """ Convert RST to xetex. """

        writer = xetex.Writer ()
        destination = io.StringOutput (encoding = 'unicode')

        overrides = {
            'doctitle_xform': 1,
            'sectsubtitle_xform': 1,
            'footnote_references': 'superscript',
            'compact_lists': 1,
            'compact_simple': 1,
            'page_numbers': 1,
            'format': options.type,
            'encoding': 'utf-8',
            'get_resource': self.get_resource,
            'get_image_size': self.get_image_size_from_parser,
            'no_images': not self.options.want_images,
            'base_url': self.url,
            }

        doc = self._full_parse (writer, overrides)
        return writer.write (doc, destination)


    def rst2htmlish (self, writer, more_overrides = {}):

        destination = io.StringOutput (encoding = 'unicode')

        overrides = {
            'stylesheet': None,
            'stylesheet_path': None,
            'xml_declaration': 0,
            'doctitle_xform': 1,
            'initial_header_level': 2,
            'sectsubtitle_xform': 1,
            'footnote_references': 'superscript',
            'page_numbers': 1,
            'format': options.type,
            'encoding': 'utf-8',
            'get_resource': self.get_resource,
            'get_image_size': self.get_image_size_from_parser,
            'no_images': not self.options.want_images,
            'base_url': self.url,
            }
        overrides.update (more_overrides)

        doc = self._full_parse (writer, overrides)
        return writer.fixup_xhtml (self.to_xhtml (writer.write (doc, destination), self.url))


    def rst2html (self):
        """ Convert RST input to HTML output. """
        return self.rst2htmlish (xhtml1.Writer ())


    def rst2epub2 (self):
        """ Convert RST input to HTML output with Epub2 tweaks. """
        return self.rst2htmlish (epub2.Writer (), 
                                 { 'toc_backlinks': 'none' })


    def get_resource (self, package, resource):
        return (resource_string ('epubmaker.' + package, resource))


    def get_image_size_from_parser (self, uri):
        # debug ("Getting image dimen for %s" % uri)
        parser = ParserFactory.ParserFactory.create (uri, {})
        parser.pre_parse ()
        if hasattr (parser, 'get_image_dimen'):
            return parser.get_image_dimen ()
        return None


    def get_charset_from_rstheader (self):
        """ Parse text for hints about charset. """
        # .. -*- coding: utf-8 -*-
        
        charset = None
        rst = self.bytes_content ()
        
        match = RE_EMACS_CHARSET.search (rst)
        if (match):
            charset = match.group (1)
            debug ('Got charset %s from emacs comment' % charset)

        return charset


    def parse (self):
        """ Dummy. Use rst2* instead. """

        debug ("Done parsing %s" % self.url)
