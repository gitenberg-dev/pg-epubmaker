#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

Parser Package

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

"""

import re
import urlparse

import lxml.html
from lxml import etree
from lxml.builder import ElementMaker

import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import NS, xpath
from epubmaker.lib.Logger import info, debug, error


RE_GUTENBERG    = re.compile (r'Project Gutenberg',         re.I)
RE_AUTHOR       = re.compile (r"^Author:\s+(.+)$",          re.I | re.M)
RE_TITLE        = re.compile (r"^Title:\s+(.+)$",           re.I | re.M)
RE_LANGUAGE     = re.compile (r"^Language:\s+(.+)$",        re.I | re.M)
# Release Date: September 5, 2009 [EBook #29915]
RE_RELEASEDATE  = re.compile (r"^(Release|Posting)\s+Date:\s+(.+)\[", re.I | re.M)
RE_EBOOKNO      = re.compile (r'\[E(?:Book|Text) #(\d+)\]', re.I | re.M)

RE_XML_CHARSET  = re.compile (r'^<\?xml.*encoding\s*=\s*["\']([^"\'\s]+)',  re.I)
RE_HTML_CHARSET = re.compile (r';\s*charset\s*=\s*([^"\'\s]+)',             re.I)
RE_PG_CHARSET   = re.compile (r"^Character Set Encoding:\s+([-\w\d]+)\s*$", re.I | re.M)


# XML 1.1 RestrictedChars 
# [#x1-#x8] | [#xB-#xC] | [#xE-#x1F] | [#x7F-#x84] | [#x86-#x9F]
RE_RESTRICTED   = re.compile (u'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')

XML_NAMESTARTCHAR = u':A-Z_a-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u02ff' \
                    u'\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f' \
                    u'\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd'
                    # u'\U00010000-\U000effff'
XML_NAMECHAR = u'-.0-9\u00b7\u0300-\u036f\u203f-\u2040' + XML_NAMESTARTCHAR

RE_XML_NAME = re.compile ('^[%s][%s]*$' % (XML_NAMESTARTCHAR, XML_NAMECHAR))

URI_MARK_CHARS     = u"-_.!~*'()"
URI_RESERVED_CHARS = u';/?:@&=+$,'

RE_URI_FRAGMENT = re.compile (u'[' + URI_MARK_CHARS + URI_RESERVED_CHARS + u'%A-Za-z0-9]+')

# all bogus encoding names used in PG go in here
BOGUS_CHARSET_NAMES = { 'iso-latin-1': 'iso-8859-1',
                        'big5'       : 'big5hkscs', 
                        'big-5'      : 'big5hkscs', 

                        # python has bogus codec name
                        'macintosh'  : 'mac_roman',
                        }


class ParserBase (object):
    """ Base class for more specialized parsers. """

    def __init__ (self):
        self.orig_url       = None
        self.url            = None
        self.mediatype      = None
        self.attribs        = {}
        self.encoding       = None
        self.fp             = None
        self.id             = None

        self.buffer         = None
        self.options        = None
        

    def setup (self, orig_url, mediatype, attribs, fp):
        """ Set url, mediatype and file object. """
        self.orig_url       = orig_url
        self.mediatype      = mediatype
        self.attribs        = attribs
        self.fp             = fp
        self.url            = fp.geturl ()
        self.buffer         = None


    def pre_parse (self):
        """ Do a lightweight parse, that allows iterlinks () to succeed.  

        Spider.py needs to use iterlinks () to grab dependencies, but
        does not need a full parse. If a lightweight parse doesn't
        make sense, you may also do a full parse here and save the
        result.

        """
        pass


    def parse (self):
        """ Do a full parse. 

        When this gets called, a pre_parse has already been done,
        so you might safely reuse any cached results.

        """

        pass


    @staticmethod
    def _get_charset_from_mediatype (mediatype, source = ''):
        """ Get charset from mediatype. """

        charset = None
        
        if mediatype:
            match = RE_HTML_CHARSET.search (mediatype)
            if (match):
                charset = match.group (1)
                debug ('Got charset %s from %s' % (charset, source))
            
        return charset
        

    def get_charset_from_content_type (self):
        """ Get charset from server content-type. """
        return self._get_charset_from_mediatype (self.mediatype, 'server')
        

    def get_charset_from_link_type (self):
        """ Get charset from link type attribute. """
        return self._get_charset_from_mediatype (self.attribs.get ('mediatype'), 'link')
        

    def get_charset_from_meta (self): # pylint: disable=R0201
        """ Parse header metadata for hints about charset.

        Override this in htmlish parsers.

        """
        
        return None


    def get_charset_from_pgheader (self): # pylint: disable=R0201
        """ Parse text for hints about charset.

        Override this in gutenberg txt parser.

        """
        
        return None


    def get_charset_from_rstheader (self): # pylint: disable=R0201
        """ Parse text for hints about charset.

        Override this in rst parser.

        """
        
        return None


    def guess_charset_from_body (self):
        """ guess from text contents """

        encoding = None
        text = self.bytes_content ()

        # BOM
        if text[:3] == '\xef\xbb\xbf':
            return 'utf-8'
        
        if re.search ('[\x81\x8d\x90\x9d]', text):
            encoding = 'cp437'

        tests = { 
            # daß
            "\bda\xe1\b"    : 'cp437', 
            "\bda\xdf\b"    : 'iso-8859-1',
            # même
            "\bm\x88me\b"   : 'cp437',
            "\bm\xeame\b"   : 'iso-8859-1',
            # été
            "\b\x82t\x82\b" : 'cp437',
            "\b\xe9t\xe9\b" : 'iso-8859-1',
        }

        if encoding is None:
            for test, enc in tests.items ():
                if re.search (test, text) > -1:
                    encoding = enc

        if encoding == 'cp437':
            if text.find ('\xd4') > -1:
                # È
                encoding = 'cp850'
        
        if encoding == 'iso-8859-1':
            if re.search ('[\x80-\x9f]', text):
                encoding = 'windows-1252'

        return encoding or 'windows-1252'


    def bytes_content (self):
        """ Get document content as raw bytes. """

        if self.buffer is None:
            try:
                debug ("Fetching %s ..." % self.fp.geturl ())
                self.buffer = self.fp.read ()
                self.fp.close ()
            except IOError, what:
                error (what)
                
        return self.buffer
        

    def unicode_content (self):
        """ Get document content as unicode string. """

        data = (self.decode (self.get_charset_from_content_type ()) or
                self.decode (self.get_charset_from_meta ()) or
                self.decode (self.get_charset_from_rstheader ()) or
                self.decode (self.get_charset_from_link_type ()) or
                self.decode (self.get_charset_from_pgheader ()) or
                self.decode ('us-ascii') or
                self.decode (self.guess_charset_from_body ()))
        
        if not data:
            raise UnicodeError ("Text in Klingon encoding ... giving up.")

        if u'\r' in data or u'\u2028' in data:
            data = u'\n'.join (data.splitlines ())
            
        return RE_PG_CHARSET.sub ('', data)


    def decode (self, charset):
        """ Try to decode document contents to unicode. """
        if charset is None:
            return None

        charset = charset.lower ().strip ()
        
        if charset in BOGUS_CHARSET_NAMES:
            charset = BOGUS_CHARSET_NAMES[charset]

        if charset == 'utf-8':
            charset = 'utf_8_sig'

        try:
            debug ("Trying charset %s ..." % charset)
            self.encoding = charset
            return self.bytes_content ().decode (charset)
        except LookupError, what:
            # unknown charset, 
            self.encoding = None
            error ("Invalid charset name: %s (%s)" % (charset, what))
        except UnicodeError, what:
            # mis-stated charset, did not decode 
            self.encoding = None
            error ("Text not in charset %s" % (charset))
        return None
    

    # Links are found in HTMLParserBase and CSSParser. These methods
    # are overwritten there.

    def iterlinks (self): # pylint: disable=R0201
        """ Return all links in document. 

        returns a list of url, dict 
        dict may contain any of: tag, id, rel, type.

        """
            
        return []
        

    def rewrite_links (self, dummy_f): # pylint: disable=R0201
        """ Rewrite all links using the function f. """
        return


    def remap_links (self, dummy_url_map): # pylint: disable=R0201
        """ Rewrite all links using the dictionary url_map. """
        return


em = ElementMaker (makeelement = lxml.html.xhtml_parser.makeelement,
                   namespace = str (NS.xhtml),
                   nsmap = { None: str (NS.xhtml) })


class HTMLParserBase (ParserBase):
    """ Base class for more HTMLish parsers.

    (HTMLParser, GutenbergTextParser)

    """

    def __init__ (self):
        ParserBase.__init__ (self)
        self.xhtml = None


    def setup (self, orig_url, mediatype, attribs, fp):
        """ Set url, mediatype and file object. """
        ParserBase.setup (self, orig_url, mediatype, attribs, fp)

        # A parser derived from HTMLParserBase should return every
        # format it parses (eg. html, txt, rss) as valid xhtml.
        self.mediatype = 'application/xhtml+xml'


    @staticmethod
    def add_class (elem, class_):
        """ Add a class to html element. """
        classes = elem.get ('class', '').split ()
        classes.append (class_)
        elem.set ('class', ' '.join (classes))


    def get_charset_from_meta (self):
        """ Parse text for hints about charset. """
        
        charset = None
        html = self.bytes_content ()
        
        match = RE_XML_CHARSET.search (html)
        if (match):
            charset = match.group (1)
            debug ('Got charset %s from xml declaration' % charset)
        else:
            match = RE_HTML_CHARSET.search (html)
            if (match):
                charset = match.group (1)
                debug ('Got charset %s from html meta' % charset)

        return charset


    def iterlinks (self):
        """ Return all links in document. """

        # First we determine the coverpage url.  In HTML we find the
        # coverpage by appling these rules:
        #
        #   1. the image specified in <link rel='coverpage'>,
        #   2. the image with an id of 'coverpage' or
        #   3. the image with an url containing 'cover'
        #   4. the image with an url containing 'title'
        #
        # If one rule returns images we take the first one in document
        # order, else we proceed with the next rule.

        coverpages = xpath (self.xhtml, "//link[@rel='coverpage']")
        if not coverpages:
            coverpages = xpath (self.xhtml, "//img[@id='coverpage']")
        if not coverpages:
            coverpages = xpath (self.xhtml, "//img[contains (@url, 'cover')]")
        if not coverpages:
            coverpages = xpath (self.xhtml, "//img[contains (@url, 'title')]")
        if coverpages:
            coverpages[0].set ('rel', 'coverpage')

        for (elem, dummy_attribute, url, dummy_pos) in self.xhtml.iterlinks ():
            d = {'tag': elem.tag }
            a = elem.attrib
            for name in ('id', 'rel', 'type'):
                if name in a:
                    d[name] = a[name]
            yield url, d
        

    def rewrite_links (self, f):
        """ Rewrite all links using the function f. """
        self.xhtml.rewrite_links (f)


    def remap_links (self, url_map):
        """ Rewrite all links using the dictionary url_map. """
        def f (url):
            """ Remap function """
            ur, frag = urlparse.urldefrag (url)
            if ur in url_map:
                debug ("Rewriting redirected url: %s to %s" % (ur, url_map[ur]))
                ur = url_map[ur]
            return "%s#%s" % (ur, frag) if frag else ur
            
        self.rewrite_links (f)


    @staticmethod
    def strip_links (xhtml, manifest):
        """ Strip all links to urls not in manifest.

        This includes <a href>, <link href> and <img src>
        Assume links and urls are already made absolute.

        """
        
        for link in xpath (xhtml, '//xhtml:a[@href]'):
            href = urlparse.urldefrag (link.get ('href'))[0]
            if href not in manifest:
                debug ("strip_links: Deleting <a> to %s not in manifest." % href)
                del link.attrib['href']

        for link in xpath (xhtml, '//xhtml:link[@href]'):
            href = link.get ('href')
            if href not in manifest:
                debug ("strip_links: Deleting <link> to %s not in manifest." % href)
                link.drop_tree ()
                
        for image in xpath (xhtml, '//xhtml:img[@src]'):
            src = image.get ('src')
            if src not in manifest:
                debug ("strip_links: Deleting <img> with src %s not in manifest." % src)
                image.tail = image.get ('alt', '') + (image.tail or '')
                image.drop_tree ()

                
    def make_toc (self, xhtml):
        """ Build a TOC from HTML headers.

        Return a list of tuples (url, text, depth).

        Page numbers are also inserted because DTBook NCX needs the
        play_order to be sequential.
        
        """

        def id_generator (i = 0):
            """ Generate an id for the TOC to link to. """
            while True:
                yield 'pgepubid%05d' % i
                i += 1

        idg = id_generator ()
        
        def get_id (elem):
            """ Get the id of the element or generate and set one. """
            if not elem.get ('id'):
                elem.set ('id', idg.next ()) # pylint: disable=E1101
            return elem.get ('id')

        toc = []
        last_depth = 0

        for header in xpath (xhtml, 
            '//xhtml:h1|//xhtml:h2|//xhtml:h3|//xhtml:h4|'
            # DP page number
            '//xhtml:*[contains (@class, "pageno")]|'
            # DocUtils contents header
            '//xhtml:p[contains (@class, "topic-title")]'):

            text = gg.normalize (etree.tostring (header,
                                                 method = "text",
                                                 encoding = unicode,
                                                 with_tail = False))
            
            text = header.get ('title', text).strip ()

            if not text:
                # so <h2 title=""> may be used to suppress TOC entry
                continue

            if header.get ('class', '').find ('pageno') > -1:
                toc.append ( ["%s#%s" % (self.url, get_id (header)), text, -1] )
            else:
                # header
                if text.lower ().startswith ('by '):
                    # common error in PG: <h2>by Lewis Carroll</h2> should
                    # yield no TOC entry
                    continue

                try:
                    depth = int (header.tag[-1:])
                except ValueError:
                    depth = 2 # avoid top level 

                # fix bogus header numberings
                if depth > last_depth + 1:
                    depth = last_depth + 1

                last_depth = depth

                # if <h*> is first element of a <div> use <div> instead
                parent = header.getparent ()
                if (parent.tag == NS.xhtml.div and
                    parent[0] == header and
                    parent.text and
                    parent.text.strip () == ''):
                    header = parent
                    
                toc.append ( ["%s#%s" % (self.url, get_id (header)), text, depth] )

        return toc


    def serialize (self):
        """ Serialize to string. """

        return etree.tostring (self.xhtml, 
                               # FIXME: how can we trigger XHTML compatible serialization?
                               doctype = gg.XHTML_DOCTYPE, 
                               xml_declaration = True,
                               encoding = 'utf-8', 
                               pretty_print = True)
