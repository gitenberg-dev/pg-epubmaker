#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

Spider.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Rudimentary Web Spider

"""

from __future__ import with_statement

import urlparse
import fnmatch

from epubmaker.lib import MediaTypes
import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import NS
from epubmaker.lib.Logger import debug

from epubmaker import ParserFactory

COVERPAGE_MIN_AREA = 200 * 200

class Spider (object):
    """ A very rudimentary web spider. """

    def __init__ (self):
        self.options = None
        self.parsed_urls = set ()
        self.enqueued_urls = set ()
        self.included_mediatypes = set ()
        self.excluded_mediatypes = set ()
        self.queue = []
        self.parsers = []
        self.next = [] # for a topological sort
        self.redirection_map = {}


    def parse (self, url, mediatype_hint, options):
        """ Do a recursive parse starting from url.
        
        Do a breadth-first traversal. Assuming the first page contains
        a linked TOC, this will get us a more natural ordering of the
        pages than a depth-first traversal.

        """

        self.options = options

        for rewrite in self.options.rewrite:
            from_, to = rewrite.split ('>')
            self.redirection_map[from_] = to

        debug ("Start of retrieval")

        # enqueue root url
        
        attribs = { 'mediatype' : mediatype_hint, 'id': 'start' }
        self.enqueue (url, 0, attribs)

        while self.queue:
            (url, depth, attribs) = self.queue.pop (0)

            url = self.redirect (url)
            if url in self.parsed_urls:
                continue
            
            parser = ParserFactory.ParserFactory.create (url, attribs)
            self.add_redirection (parser)
            
            # if the url was redirected to something we already have
            url = self.redirect (parser.url)
            if url in self.parsed_urls:
                continue
            
            self.parsed_urls.add (url)
            parser.options = self.options
            parser.pre_parse ()
            self.parsers.append (parser)

            # check potential coverpage for sufficient size
            if options.coverpage_url is None:
                if attribs.get ('rel', '') == 'coverpage':
                    if hasattr (parser, 'get_image_dimen'):
                        dimen = parser.get_image_dimen ()
                        if (dimen[0] * dimen[1]) > COVERPAGE_MIN_AREA:
                            options.coverpage_url = parser.url
                            debug ("Setting coverpage: %s ..." % parser.url)

            depth += 1

            # look for links in just parsed document
            debug ("Requesting iterlinks for: %s ..." % url)

            for (url, attr) in parser.iterlinks ():
                # debug ("*** link: %s ..." % url)

                url = urlparse.urldefrag (url)[0]
                tag = attr.get ('tag', '')

                if tag == NS.xhtml.link:
                    if attr.get ('rel', '').lower () == 'next':
                        self.next.append ((parser.url, url))
                
                url = self.redirect (url)

                attribs = { 'mediatype' : attr.get ('type', None) }

                for k in ('id', 'rel'):
                    if k in attr:
                        attribs[k] = attr[k]
                
                if tag == NS.xhtml.a:
                    self.enqueue_doc (url, depth, attribs)
                    continue
                if tag == NS.xhtml.img:
                    self.enqueue_aux (url, depth, attribs)
                    continue
                if tag == NS.xhtml.object:
                    if ('type' in attr and
                        not self.is_included_mediatype (attr['type'])):
                        continue
                    self.enqueue_aux (url, depth, attribs)
                    continue
                if tag == NS.xhtml.link:
                    rel = attribs.get ('rel', '').lower ()
                    if 'stylesheet' in rel:
                        self.enqueue_aux (url, depth, attribs)
                    elif rel == 'coverpage':
                        # We may also find the coverpage in <link rel='coverpage' href='url' />
                        self.enqueue_aux (url, depth, attribs)
                    else:
                        self.enqueue_doc (url, depth, attribs)
                    continue
                    
        debug ("End of retrieval")
        
        # rewrite redirected urls
        if self.redirection_map:
            for parser in self.parsers:
                parser.remap_links (self.redirection_map)

        # try a topological sort of documents using <link rel='next'>
        if self.next:
            self.next = map (lambda x: (self.redirect(x[0]), self.redirect(x[1])), self.next)

            try:
                d = {}
                for order, url in enumerate (gg.topological_sort (self.next)):
                    d[url] = order
                    debug ("%s order %d" % (url, order))
                for parser in self.parsers:
                    parser.order = d.get (parser.url, 999999)
                self.parsers.sort (key = lambda p: p.order)
                
            except StandardError:
                pass


    def add_redirection (self, parser):
        """ Remember this redirection. """
        if parser.orig_url != parser.url:
            self.redirection_map[parser.orig_url] = parser.url
            debug ("Adding redirection from %s to %s" % (parser.orig_url, parser.url))

        
    def redirect (self, url):
        """ Redirect url if we know the target. """
        return self.redirection_map.get (url, url)

        
    def enqueue (self, url, depth, attribs):
        """ Enque url for parsing. """
        
        url = self.redirect (url)
        if url in self.enqueued_urls:
            return
        
        debug ("Enqueing %s ..." % url)
        self.queue.append ((url, depth, attribs))
        self.enqueued_urls.add (url)
        
            
    def enqueue_aux (self, url, depth, attribs):
        """ Enqueue an auxiliary file.

        We get auxiliary files even if they are too deep or not in
        'included' directories.

        """
        
        parser = ParserFactory.ParserFactory.create (url, attribs)
        self.add_redirection (parser)
        if self.is_wanted_aux (parser):
            self.enqueue (parser.url, depth, attribs)


    def enqueue_doc (self, url, depth, attribs):
        """ Enqueue a document file.

        We get document files only if they pass document-selection
        rules.

        """
        
        if not self.options.max_depth or depth < self.options.max_depth:
            if self.is_included (url):
                parser = ParserFactory.ParserFactory.create (url, attribs)
                self.add_redirection (parser)
                if self.is_wanted_doc (parser):
                    self.enqueue (parser.url, depth, attribs)


    def is_included (self, url):
        """ Return True if this document is eligible. """

        included = any (map (lambda x: fnmatch.fnmatchcase (url, x), self.options.include))
        excluded = any (map (lambda x: fnmatch.fnmatchcase (url, x), self.options.exclude))

        if included and not excluded:
            return 1

        if excluded:
            debug ("Dropping excluded %s" % url)
        if not included:
            debug ("Dropping not included %s" % url)
        return 0
            

    def is_included_mediatype (self, mediatype):
        """ Return True if this document is eligible. """

        included = any (map (lambda pattern: fnmatch.fnmatch (mediatype, pattern),
                             self.options.include_mediatypes))
        excluded = any (map (lambda pattern: fnmatch.fnmatch (mediatype, pattern),
                             self.options.exclude_mediatypes))

        if included and not excluded:
            self.included_mediatypes.add (mediatype)
            return 1

        if excluded:
            debug ("Dropping excluded mediatype %s" % mediatype)
        if not included:
            debug ("Dropping not included mediatype %s" % mediatype)
            
        self.excluded_mediatypes.add (mediatype)
        return 0
            

    def has_seen_images (self):
        """ Return True if the spider has encountered images. """

        return bool (MediaTypes.IMAGE_MEDIATYPES &
                       (self.included_mediatypes | self.excluded_mediatypes))

        
    def dict_urls_mediatypes (self):
        """ Return a dict of all parsed urls and mediatypes. """
        return dict (map (lambda p: (p.url, p.mediatype), self.parsers))
    

    def is_wanted_doc (self, parser):
        """ Return True if we ought to parse this content document.

        Override this in custom spiders.

        """
        return self.is_included_mediatype (parser.mediatype)


    def is_wanted_aux (self, parser):
        """ Return True if we ought to parse this image or aux file.

        Override this in custom spiders.

        """
        return self.is_included_mediatype (parser.mediatype)


