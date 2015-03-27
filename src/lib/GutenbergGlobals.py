#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""
GutenbergGlobals.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

This module has sadly decayed into a repository for all sorts of cruft.

FIXME: refactor this module

"""

import os
import re
import datetime

class Struct (object):
    """ handy class to pin attributes on

    usage: c = Struct ()
           c.something = 1

    """
    pass


NSMAP = {
    'atom':       'http://www.w3.org/2005/Atom',
    'bio':        'http://purl.org/vocab/bio/0.1/',
    'cc':         'http://web.resource.org/cc/',
    'dc':         'http://purl.org/dc/elements/1.1/',
    'dcam':       'http://purl.org/dc/dcam/',
    'dcmitype':   'http://purl.org/dc/dcmitype/',
    'dcterms':    'http://purl.org/dc/terms/',
    'ebook':      'http://www.gutenberg.org/ebooks/',             # URL
    'foaf':       'http://xmlns.com/foaf/0.1/',
    'marcrel':    'http://id.loc.gov/vocabulary/relators',
    'mathml':     'http://www.w3.org/1998/Math/MathML',
    'mbp':        'http://mobipocket.com/mbp',
    'ncx':        'http://www.daisy.org/z3986/2005/ncx/',
    'opds':       'http://opds-spec.org/2010/Catalog',
    'opf':        'http://www.idpf.org/2007/opf',
    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
    'pg':         'http://www.gutenberg.org/',                    # URL
    'pgagents':   'http://www.gutenberg.org/2009/agents/',
    'pgtei':      'http://www.gutenberg.org/tei/marcello/0.5/ns',
    'pgterms':    'http://www.gutenberg.org/2009/pgterms/',
    'py':         'http://genshi.edgewall.org/',
    'rdf':        'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs':       'http://www.w3.org/2000/01/rdf-schema#',
    'svg':        'http://www.w3.org/2000/svg',
    'tei':        'http://www.tei-c.org/ns/1.0',
    'xhtml':      'http://www.w3.org/1999/xhtml',
    'xinclude':   'http://www.w3.org/2001/XInclude',
    'xml':        'http://www.w3.org/XML/1998/namespace',
    'xmlns':      'http://www.w3.org/2000/xmlns/',
    'xsd':        'http://www.w3.org/2001/XMLSchema#',
    'xsi':        'http://www.w3.org/2001/XMLSchema-instance',
    'xslfo':      'http://www.w3.org/1999/XSL/Format',
}


class NameSpaceClark (object):
    """ Build a tag name in Clark notation.

    ns = NameSpaceClark ("http://example.com/")
    >>> ns.foo
    '{http://example.com/}foo'
    >>> ns['bar']
    '{http://example.com/}bar'

    """

    def __init__ (self, root):
        self.root = root

    def __getitem__ (self, local):
        return "{%s}%s" % (self.root, local)

    def __getattr__ (self, local):
        return "{%s}%s" % (self.root, local)

    def __str__ (self):
        return self.root


class NameSpaceURI (object):
    """ Build a URI.

    ns = NameSpaceURI ("http://example.com/")
    >>> ns.foo
    'http://example.com/foo'
    >>> ns['bar']
    'http://example.com/bar'

    """

    def __init__ (self, root):
        self.root = root

    def __getitem__ (self, local):
        return "%s%s" % (self.root, local)

    def __getattr__ (self, local):
        return "%s%s" % (self.root, local)

    def __str__ (self):
        return self.root


def build_nsmap (prefixes = None):
    """ build a nsmap containing all namespaces for prefixes """

    if prefixes is None:
        prefixes = NSMAP.keys ()
    if isinstance (prefixes, str):
        prefixes = prefixes.split ()

    ns = {}
    for prefix in prefixes:
        ns[prefix] = NSMAP[prefix]

    return ns


NS = Struct ()
NSURI = Struct ()

for prefix, uri in NSMAP.items ():
    setattr (NS, prefix, NameSpaceClark (uri))
    setattr (NSURI, prefix, NameSpaceURI (uri))

XML_DECLARATION = """<?xml version='1.0' encoding='UTF-8'?>"""

XHTML_DOCTYPE   = ("<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.1//EN' " +  
                   "'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd'>")

XHTML1_DOCTYPE   = ("<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML 1.0 Strict//EN' " +  
                   "'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'>")

XHTML_RDFa_DOCTYPE = ("<!DOCTYPE html PUBLIC '-//W3C//DTD XHTML+RDFa 1.0//EN' " +
                      "'http://www.w3.org/MarkUp/DTD/xhtml-rdfa-1.dtd'>")

NCX_DOCTYPE = ("<!DOCTYPE ncx PUBLIC '-//NISO//DTD ncx 2005-1//EN' " +
               "'http://www.daisy.org/z3986/2005/ncx-2005-1.dtd'>")

GENERATOR = 'EpubMaker 0.3 by Marcello Perathoner <webmaster@gutenberg.org>'


def xmlspecialchars (s):
    return (s.replace (u'&',  u'&amp;')
             .replace (u'<',  u'&lt;')
             .replace (u'>',  u'&gt;'))

def insert_breaks (s):
    return s.replace (u'\n',  u'<br />')

RE_NORMALIZE    = re.compile (r"\s+")

def normalize (s):
    s = RE_NORMALIZE.sub (' ', s)
    return s.strip ()


def cut_at_newline (text):
    """ Cut the text at the first newline. """
    i = text.find ('\n')
    if i > -1:
        return text[:i]
    return text

def archive_dir (ebook):
    """ build 1/2/3/4/12345 for 12345 """
    ebook = str (ebook)
    a = []
    for c in ebook:
        a.append (c)
    a[-1] = ebook
    return "/".join (a)

def archive2files (ebook, path):
    adir = archive_dir (ebook)
    return path.replace ('dirs/' + adir, 'files/%d' % ebook)


def xpath (node, path, **kwargs):
    """ xpath helper """
    return node.xpath (path, namespaces = NSMAP, **kwargs)


def mkdir_for_filename (fn):
    """ Make sure the directory for this file is present. """

    try:
        os.makedirs (os.path.dirname (fn))
    except os.error:
        pass


def make_url_relative (base_url, url):
    """ Make absolute url relative to base_url if possible. """

    if (url.startswith (base_url)):
        return url[len (base_url):]

    base_url = os.path.dirname (base_url) + '/'

    if (url.startswith (base_url)):
        return url[len (base_url):]

    return url


def normalize_path (path):
    """ Normalize a file path. """
    if path.startswith ('file://'):
        path = path[7:]
    return path
        
def is_same_path (path1, path2):
    """ Does path1 point to the same file as path2? """
    return os.path.realpath (normalize (path1)) == os.path.realpath (normalize (path2))


def string_to_filename (fn):
    """ Sanitize string so it can do as filename. """

    def escape (matchobj):
        """ Escape a char. """
        return '@%x' % ord (matchobj.group (0))

    fn = os.path.normpath (fn)
    fn = normalize (fn)
    fn = fn.replace (os.sep, '@')
    if os.altsep:
        fn = fn.replace (os.altsep, '@')
    fn = re.sub (u'[\|/:?"*<>\u0000-\u001F]', escape, fn)

    return fn
    

class DCIMT (object):
    """ encapsulates one dcterms internet mimetype 

    """

    def __init__ (self, mime, enc = None):
        if mime is None:
            self.mimetype = 'application/octet-stream'
        elif enc is not None and mime.startswith ('text/'):
            self.mimetype = "%s; charset=%s" % (mime, enc)
        else:
            self.mimetype = mime
    
    def __str__ (self):
        return self.mimetype
    

class UTC (datetime.tzinfo):
    """ UTC helper for datetime.datetime """

    def utcoffset (self, dummy_dt):
        return datetime.timedelta (0)

    def tzname (self, dummy_dt):
        return "UTC"

    def dst (self, dummy_dt):
        return datetime.timedelta (0)

# exceptions

class SkipOutputFormat (Exception):
    pass

# Spider.py treis a topological sort on link rel=next
def topological_sort (pairlist):
    """Topologically sort a list of (parent, child) pairs.

    Return a list of the elements in dependency order (parent to child order).

    >>> print topsort( [(1,2), (3,4), (5,6), (1,3), (1,5), (1,6), (2,5)] ) 
    [1, 2, 3, 5, 4, 6]

    >>> print topsort( [(1,2), (1,3), (2,4), (3,4), (5,6), (4,5)] )
    [1, 2, 3, 4, 5, 6]

    >>> print topsort( [(1,2), (2,3), (3,2)] )
    Traceback (most recent call last):
    CycleError: ([1], {2: 1, 3: 1}, {2: [3], 3: [2]})
 
    """
    num_parents = {}  # element -> # of predecessors 
    children = {}  # element -> list of successors 
    for parent, child in pairlist: 
        # Make sure every element is a key in num_parents.
        if not num_parents.has_key( parent ): 
            num_parents[parent] = 0 
        if not num_parents.has_key( child ): 
            num_parents[child] = 0 

        # Since child has a parent, increment child's num_parents count.
        num_parents[child] += 1

        # ... and parent gains a child.
        children.setdefault(parent, []).append(child)

    # Suck up everything without a parent.
    answer = [x for x in num_parents.keys() if num_parents[x] == 0]

    # For everything in answer, knock down the parent count on its children.
    # Note that answer grows *in* the loop.
    for parent in answer: 
        del num_parents[parent]
        if children.has_key( parent ): 
            for child in children[parent]: 
                num_parents[child] -= 1
                if num_parents[child] == 0: 
                    answer.append( child ) 
            # Following "del" isn't needed; just makes 
            # CycleError details easier to grasp.
            del children[parent]

    if num_parents: 
        # Everything in num_parents has at least one child -> 
        # there's a cycle.
        raise Exception (answer, num_parents, children)
    return answer 
