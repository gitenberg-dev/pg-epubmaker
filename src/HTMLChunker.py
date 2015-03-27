#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

HTMLChunker.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Splits a HTML file into chunks.

"""

from __future__ import with_statement

import urlparse
import urllib
import os
import re
import copy

from lxml import etree

import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import NS
from epubmaker.lib.Logger import debug, error

# MAX_CHUNK_SIZE  = 300 * 1024  # bytes
MAX_CHUNK_SIZE  = 100 * 1024  # bytes

SECTIONS = [
    ('div.section', 0.0), 
    ('div.chapter', 0.0), 
    ('h1',          0.5),
    ('div',         0.5),
    ('h2',          0.7),
    ('h3',          0.75),
    ('p',           0.8)
    ]

def xpath (node, path):
    """ xpath helper """
    return node.xpath (path, namespaces = gg.NSMAP)

def unicode_uri (uri):
    """ Normalize URI for idmap. """
    return urllib.unquote (uri).decode ('utf-8')


class HTMLChunker (object):
    """ Splits HTML tree into smaller chunks.

    Some epub viewers are limited in that they cannot display files
    larger than 300K.  If our HTML happens to be longer, we have to
    split it up.  Also smaller chunks do improve page flip times.


    """

    def __init__ (self):
        self.chunks = []
        self.idmap = {}
        self.chunk = None
        self.chunk_body = None
        self.chunk_size = 0
        self.next_id = 0

        self.tags = {}
        for tag, size in SECTIONS:
            self.tags[NS.xhtml[tag]] = int (size * MAX_CHUNK_SIZE)
        for tag in options.section_tags:
            self.tags[NS.xhtml[tag]] = 0
        

    def _make_name (self, url):
        """ Generate a name for the chunk. """
        u = list (urlparse.urlparse (url))
        root, ext = os.path.splitext (u[2])
        # FIXME: brain-dead kindlegen only finds links in files with
        # .html extension. so we just add .html to everything
        u[2] = "%s-%d%s.html" % (root, self.next_id, ext)
        self.next_id += 1
        return urlparse.urlunparse (u)
    
        
    @staticmethod
    def make_template (tree):
        """ Make a copy with an empty html:body.

        This makes a template into which we can paste our chunks.

        """
        
        template = copy.deepcopy (tree)

        for c in xpath (template, '//xhtml:body'):

            # descend while elem has only one child
            while len (c) == 1:
                c = c[0]

            # clear children but save attributes
            attributes = c.attrib.items ()
            c.clear ()
            # was tentative fix for patological one-element-html case
            # for child in c:
            #     c.remove (child)
            for a in attributes:
                c.set (a[0], a[1])

        # debug (etree.tostring (template))

        return template


    def reset_chunk (self, template):
        """ start a new chunk """

        self.chunk = copy.deepcopy (template)
        self.chunk_size = len (etree.tostring (self.chunk))
        self.chunk_body = xpath (self.chunk, "//xhtml:body")[0]
        while len (self.chunk_body) == 1:
            self.chunk_body = self.chunk_body[0]


    def shipout_chunk (self, url, chunk_id = None, comment = None):
        """ ready chunk to be shipped """

        if (self.chunk_size > MAX_CHUNK_SIZE):
            self.split (self.chunk, url)
            return

        url = unicode_uri (url)
        chunk_name = self._make_name (url)

        # the url of the whole page
        if not url in self.idmap:
            self.idmap[url] = chunk_name

        # fragments of the page
        for e in xpath (self.chunk, '//xhtml:*[@id]'):
            id_ = e.attrib['id']
            old_id = "%s#%s" % (url, id_)
            # key is unicode string,
            # value is uri-escaped byte string
            # if ids get cloned while chunking, map to the first one only
            if old_id not in self.idmap:
                self.idmap[old_id] = "%s#%s" % (
                    chunk_name,  urllib.quote (id_.encode ('utf-8')))

        self.chunks.append ( { 'name'     : chunk_name,
                               'id'       : chunk_id,
                               'comment'  : comment,
                               'chunk'    : self.chunk,  } )
            
        debug ("Adding chunk %s (%d bytes) %s" % (chunk_name, self.chunk_size, chunk_id))


    def split (self, tree, url):
        """ Split whole html or split chunk.

        Find some arbitrary points to do it.
    
        """

        for body in xpath (tree, "//xhtml:body"):
            # we can't split a node that has only one child
            # descend while elem has only one child
            while len (body) == 1:
                body = body[0]

            debug ("body tag is %s" % body.tag)

            template = self.make_template (tree)
            self.reset_chunk (template)

            # FIXME: is this ok ???
            # fixes patological one-element-body case
            self.chunk_body.text = body.text

            for child in body:
                if not isinstance (child, etree.ElementBase):
                    # comments, processing instructions etc. 
                    continue
                child_size = len (etree.tostring (child))

                try:
                    tags = [child.tag + '.' + c for c in child.attrib['class'].split ()]
                    tags.append (child.tag)
                except KeyError:
                    tags = [child.tag]

                for tag in tags:
                    if ((self.chunk_size + child_size > MAX_CHUNK_SIZE) or
                              (tag in self.tags and
                               self.chunk_size > self.tags[tag])):
                        
                        comment = ("Chunk: size=%d Split on %s" 
                                   % (self.chunk_size, re.sub ('^{.*}', '', tag)))
                        debug (comment)

                        # find a suitable id
                        chunk_id = None
                        for c in self.chunk_body:
                            if 'id' in c.attrib:
                                chunk_id = c.get ('id')
                                break
                        debug ("chunk id is: %s" % (chunk_id or ''))
                        
                        self.shipout_chunk (url, chunk_id, comment)
                        self.reset_chunk (template)
                        break

                self.chunk_body.append (child)
                self.chunk_size = self.chunk_size + child_size

            # fixes patological one-element-body case
            self.chunk_body.tail = body.tail
            
            chunk_id = None
            if len (self.chunk_body):
                chunk_id = self.chunk_body[0].get ('id')
            comment = "Chunk: size=%d" % self.chunk_size
            self.shipout_chunk (url, chunk_id, comment)
            self.reset_chunk (template)


    def rewrite_links (self, f):
        """ Rewrite all href and src using f (). """
        
        for chunk in self.chunks:
            # chunk['name'] = f (chunk['name'])
            
            for link in xpath (chunk['chunk'], '//xhtml:*[@href]'):
                link.set ('href', f (link.get ('href')))

            for image in xpath (chunk['chunk'], '//xhtml:*[@src]'):
                image.set ('src', f (image.get ('src')))

        for k, v in self.idmap.items ():
            self.idmap[k] = f (v)


    def rewrite_internal_links (self):
        """ Rewrite links to point into right chunks.

        Because we split the HTML into chunks, all internal links need
        to be rewritten to become links into the right chunk.
        Rewrite all internal links in all chunks.

        """
        for chunk in self.chunks:
            for a in xpath (chunk['chunk'], "//xhtml:*[@href]"):
                try:
                    uri = unicode_uri (a.get ('href'))
                    a.set ('href', self.idmap[uri])
                except KeyError:
                    ur, dummy_frag = urlparse.urldefrag (uri)
                    if ur in self.idmap:
                        error ("HTMLChunker: Cannot rewrite internal link '%s'" % uri)
        

    def rewrite_internal_links_toc (self, toc):
        """ Rewrite links to point into right chunks.

        Because we split the HTML into chunks, all internal links need
        to be rewritten to become links into the right chunk.
        Rewrite all links in the passed toc.

        """

        for entry in toc:
            try:
                entry[0] = self.idmap [unicode_uri (entry[0])]
            except KeyError:
                error ("HTMLChunker: Cannot rewrite toc entry '%s'" % entry[0]) 
                del entry


