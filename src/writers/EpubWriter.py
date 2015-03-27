#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""

EpubWriter.py

Copyright 2009-2012 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Writes an EPUB file.

"""

from __future__ import with_statement

import re
import datetime
import urllib
import urlparse
import zipfile
import time
import os
import copy
import subprocess

from lxml import etree
from lxml.builder import ElementMaker
from pkg_resources import resource_string # pylint: disable=E0611

import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import NS, xpath
from epubmaker.lib.Logger import info, debug, warn, error, exception
from epubmaker.lib.MediaTypes import mediatypes as mt 
from epubmaker import ParserFactory
from epubmaker import HTMLChunker
from epubmaker import Spider
from epubmaker import parsers
from epubmaker import writers
from epubmaker.Version import VERSION, GENERATOR

# pylint: disable=W0142

MAX_CHUNK_SIZE  = 300 * 1024  # bytes

MAX_IMAGE_SIZE  = 127 * 1024  # in bytes

MAX_IMAGE_DIMEN = (800, 1280)  # in pixels
MAX_COVER_DIMEN = (800, 1280)  # in pixels

MAX_IMAGE_SIZE_KINDLE  = 127 * 1024  # in bytes

MAX_IMAGE_DIMEN_KINDLE = (1200, 1920)  # Kindle Fire HD 8.9" in pixels
MAX_COVER_DIMEN_KINDLE = (1200, 1920)  # 

# iPhone 3G:    320x480x?
# Kindle 2:     600x800x16
# Sony PRS-505: 584x754x8   (effective according to wikipedia)


TOC_HEADERS = (u'contents', u'table of contents',
               u'inhalt', u'inhaltsverzeichnis',
               u'table des matières',
               u'indice',
               u'inhoud')

DP_PAGENUMBER_CLASSES = frozenset ('pagenum pageno page pb folionum foliono'.split ())

STRIP_CLASSES         = DP_PAGENUMBER_CLASSES | frozenset ('versenum verseno'.split ())


# Undo the more bone-headed PG and DP formattings. Set small margins
# to save on precious mobile screen real-estate.

PRIVATE_CSS = """body, body.tei.tei-text {
   color: black; 
   background-color: white; 
   margin: 0.5em;
   width: auto;
   border: 0;
   padding: 0;
   }
div, p, pre, h1, h2, h3, h4, h5, h6 {
   margin-left: 0;
   margin-right: 0
   }
div.pgebub-root-div {
   margin: 0
   }
h2 {
   page-break-before: always;
   padding-top: 1em
   }
div.figcenter span.caption {
   display: block;
   }
.pgmonospaced {
   font-family: monospace;
   font-size: 0.9em
   }
a.pgkilled {
   text-decoration: none;
   }
"""

OPS_TEXT_MEDIATYPES = set ( (
    'application/xhtml+xml',       # Used for OPS Content Documents 
    'application/x-dtbook+xml',    # Used for OPS Content Documents 
    'text/css',                    # Used for OPS CSS-subset style sheets 
    'application/xml',             # Used for Out-Of-Line XML Islands 
    'text/x-oeb1-document',        # Deprecated
    'text/x-oeb1-css',             # Deprecated
    'application/x-dtbncx+xml',    # The NCX
) )

OPS_IMAGE_MEDIATYPES = set ( (
    'image/gif',                   # Used for raster graphics
    'image/jpeg',                  # Used for raster graphics
    'image/png',                   # Used for raster graphics
    'image/svg+xml',               # Used for vector graphics
) )

OPS_CORE_MEDIATYPES = OPS_TEXT_MEDIATYPES | OPS_IMAGE_MEDIATYPES

OPS_CONTENT_DOCUMENTS = set ( (
    'application/xhtml+xml',
    'application/x-dtbook+xml',
    'text/x-oeb1-document',        # Deprecated
    'application/xml',
) )

CSS_PROPERTIES_TO_STRIP = frozenset ("""
   position
   float
   background-image
   background-position
   background-attachment
   background-repeat
   """.split ())

IMAGE_WRAPPER = """<?xml version="1.0"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>{title}</title>
    <style type="text/css">
       div {{ text-align: center }}
       img {{ max-width: 100%; }}
    </style>
  </head>
  <body>
    <div>
      <img src="{src}" alt="{title}" />
    </div>
  </body>
</html>"""


class OEBPSContainer (zipfile.ZipFile):
    """ Class representing an OEBPS Container. """

    def __init__ (self, filename, oebps_path = None):
        """ Create the zip file.

        And populate it with mimetype and container.xml files.

        """
        
        self.zipfilename = filename
        self.oebps_path = oebps_path if oebps_path else 'OEBPS/'
        
        info ('Creating Epub file: %s' % filename)

        # open zipfile
        zipfile.ZipFile.__init__ (self, filename, 'w', zipfile.ZIP_DEFLATED)

        # write mimetype
        # the OCF spec says mimetype must be first and uncompressed
        i = self.zi ()
        i.compress_type = zipfile.ZIP_STORED
        i.filename = 'mimetype'
        self.writestr (i, 'application/epub+zip')

        self.add_container_xml ('content.opf')

        self.wrappers = 0 # to generate unique filenames for wrappers


    def commit (self):
        """ Close OCF Container. """
        info ("Done Epub file: %s" % self.zipfilename)
        self.close ()


    def rollback (self):
        """ Remove OCF Container. """
        debug ("Removing Epub file: %s" % self.zipfilename)
        os.remove (self.zipfilename)

        
    def add_unicode (self, name, u):
        """ Add file to zip from unicode string. """
        i = self.zi (name)
        self.writestr (i, u.encode ('utf-8'))

        
    def add_bytes (self, name, bytes_, mediatype = None):
        """ Add file to zip from bytes string. """
        
        i = self.zi (name)
        if mediatype and mediatype in (mt.png, mt.gif, mt.jpeg):
            i.compress_type = zipfile.ZIP_STORED
        self.writestr (i, bytes_)


    def add_file (self, name, url, mediatype = None):
        """ Add file to zip from bytes string. """

        with open (url) as fp:
            self.add_bytes (name, fp.read (), mediatype)


    def zi (self, filename = None):
        """ Setup a ZipInfo. """
        z = zipfile.ZipInfo ()
        z.date_time = time.gmtime ()
        z.compress_type = zipfile.ZIP_DEFLATED
        z.external_attr = 0x81a40000
        if filename:
            z.filename = os.path.join (self.oebps_path, filename)
        return z


    def add_container_xml (self, rootfilename):
        """ Write container.xml
        
        <?xml version='1.0' encoding='UTF-8'?>

        <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container'
                   version='1.0'>
          <rootfiles>
            <rootfile full-path='$path'
                      media-type='application/oebps-package+xml' />
          </rootfiles>
        </container>

        """

        rootfilename = os.path.join (self.oebps_path, rootfilename)

        ns_oasis = 'urn:oasis:names:tc:opendocument:xmlns:container'

        ocf = ElementMaker (namespace = ns_oasis, 
                            nsmap = { None: ns_oasis } )

        container = ocf.container (
            ocf.rootfiles (
                ocf.rootfile (**{
                    'full-path': rootfilename,
                    'media-type': 'application/oebps-package+xml'})),
            version = '1.0')
            
        i = self.zi ()
        i.filename = 'META-INF/container.xml'
        self.writestr (i, etree.tostring (container,
            encoding = 'utf-8', xml_declaration = True, pretty_print = True))


    def add_image_wrapper (self, img_url, img_title):
        """ Add a HTML file wrapping img_url. """
        
        filename = 'wrap%04d.html' % self.wrappers
        self.wrappers += 1
        self.add_bytes (filename,
                        IMAGE_WRAPPER.format (src = img_url, title = img_title),
                        mt.xhtml)
        return filename
    

class AdobePageMap (object):
    """ Class that builds a page-map xml file. """
    
    def __init__ (self, ncx):
        self.toc = ncx.toc
        

    def __unicode__ (self):
        """ Serialize page-map as unicode string. """
        
        pm = ElementMaker (namespace = str (NS.opf),
                           nsmap = { None: str (NS.opf) })

        root = pm ('page-map')
        
        for href, name, depth in self.toc:
            if depth == -1:
                root.append (pm.page (name = name, href = href))

        page_map = u"%s\n\n%s" % (gg.XML_DECLARATION, 
                                  etree.tostring (root,
                                                  encoding = unicode,
                                                  pretty_print = True))
        debug (page_map)
        return page_map


class TocNCX (object):
    """ Class that builds toc.ncx. """
    
    def __init__ (self, dc):
        self.toc = []
        self.dc = dc
        self.seen_urls = {}
        self.ncx = ElementMaker (namespace = str (NS.ncx),
                                 nsmap = { None: str (NS.ncx) })


    def __unicode__ (self):
        """ Serialize toc.ncx as unicode string. """
        ncx = self.ncx
        tocdepth = 1

        if self.toc:
            # flatten toc if it contains only one top-level entry
            top_level_entries = sum (t[2] == 1 for t in self.toc)
            if top_level_entries < 2:
                for t in self.toc:
                    if t[2] != -1:
                        t[2] = max (1, t[2] - 1)
        
            tocdepth = max (t[2] for t in self.toc)

        head = ncx.head (
            ncx.meta (name = 'dtb:uid',            content = self.dc.opf_identifier),
            ncx.meta (name = 'dtb:depth',          content = str (tocdepth)),
            ncx.meta (name = 'dtb:generator',      content = GENERATOR % VERSION),
            ncx.meta (name = 'dtb:totalPageCount', content = '0'),
            ncx.meta (name = 'dtb:maxPageNumber',  content = '0'))

        doc_title = ncx.docTitle (ncx.text (self.dc.title))

        self.seen_urls = {}
        has_pages = False
        for url, dummy_title, depth in self.toc:
            # navPoints and pageTargets referencing the same element
            # must have the same playOrder
            if url not in self.seen_urls:
                self.seen_urls[url] = str (len (self.seen_urls) + 1)
            if depth == -1:
                has_pages = True

        params = {'version': '2005-1' }
        if self.dc.languages:
            params[NS.xml.lang] = self.dc.languages[0].id
            
        ncx = ncx.ncx (
            head,
            doc_title,
            self._make_navmap (self.toc),
            **params)

        if has_pages:
            ncx.append (self._make_pagelist (self.toc))


        # Ugly workaround for error: "Serialisation to unicode must not
        # request an XML declaration"

        toc_ncx = u"%s\n\n%s" % (gg.XML_DECLARATION,
                                 etree.tostring (ncx,
                                                 doctype = gg.NCX_DOCTYPE,
                                                 encoding = unicode,
                                                 pretty_print = True))
        # debug (toc_ncx)
        return toc_ncx


    def rewrite_links (self, f):
        """ Rewrite all links f (). """
        for entry in self.toc:
            entry[0] = f (entry[0])

    
    def _make_navmap (self, toc):
        """ Build the toc. """
        ncx = self.ncx

        root = ncx.navMap ()
        last_np_with_depth = { 0: root }

        count = 0
        for url, title, depth in toc:
            if depth > -1:
                count += 1
                np = ncx.navPoint (
                    ncx.navLabel (ncx.text (title)),
                    ncx.content (src = url),
                    **{'id'       : "np-%d" % count, 
                       'playOrder': self.seen_urls[url] })

                try:
                    parent = last_np_with_depth[depth - 1]
                    parent.append (np)
                    last_np_with_depth[depth] = np
                except KeyError:
                    warn ("Bogus depth %d in TOC" % depth)

        return root


    def _make_pagelist (self, toc):
        """ Build the page list. """
        ncx = self.ncx

        root = ncx.pageList (
            ncx.navLabel (ncx.text ('Pages')),
            # both attributes are optional in the spec,
            # but epubcheck 1.0.3 requires them
            **{'id': 'pages',
               'class': 'pagelist'})
        
        for url, pagename, depth in toc:
            if depth == -1:
                pt = ncx.pageTarget (
                    ncx.navLabel (ncx.text (pagename)),
                    ncx.content (src = url),
                    **{'id'       : "pt-%d" % len (root), 
                       'value'    : str (len (root)), # fixme: extract value
                       'type'     : 'normal' if re.search ('[0-9]', pagename) else 'front',
                       'playOrder': self.seen_urls[url] })

                root.append (pt)

        return root

    
class ContentOPF (object):
    """ Class that builds content.opf metadata. """

    def __init__ (self):
        self.nsmap = gg.build_nsmap ('opf dc dcterms xsi')

        # FIXME: remove this when lxml is fixed
        # workaround for lxml fat-fingering the default attribute namespaces
        self.nsmap[None] = str (NS.opf) + 'lxml-bug-workaround'
        
        self.opf = ElementMaker (namespace = self.nsmap[None],
                                 nsmap = self.nsmap)
        
        self.metadata = self.opf.metadata ()
        self.manifest = self.opf.manifest ()
        self.spine    = self.opf.spine ()
        self.guide    = self.opf.guide ()
        self.item_id  = 0

    
    def __unicode__ (self):
        """ Serialize content.opf as unicode string. """

        assert len (self.manifest),        'No manifest item in content.opf.'
        assert len (self.spine),           'No spine item in content.opf.'
        assert 'toc' in self.spine.attrib, 'No TOC item in content.opf.'

        package = self.opf.package (
            **{ 'version': '2.0', 'unique-identifier': 'id' })
        package.append (self.metadata)
        package.append (self.manifest)
        package.append (self.spine)
        if len (self.guide):
            package.append (self.guide)

        content_opf = u"%s\n\n%s" % (gg.XML_DECLARATION,
                                     etree.tostring (package,
                                                     encoding = unicode,
                                                     pretty_print = True))

        # FIXME: remove this when lxml is fixed
        # now merge xmlns:opf and xmlns: 
        content_opf = content_opf.replace ('lxml-bug-workaround', '')
        
        debug (content_opf)
        return content_opf


    def rewrite_links (self, f):
        """ Rewrite all links through f (). """
        for item in self.manifest:
            if item.get ('href'):
                item.set ('href', f (item.get ('href')))
        for item in self.guide:
            item.set ('href', f (item.get ('href')))
        

    def guide_item (self, url, type_, title):
        """ Add item to guide. """
        self.guide.append (
            self.opf.reference (type = type_, title = title, href = url))


    def meta_item (self, name, content):
        """ Add item to metadata. """
        self.metadata.append (self.opf.meta (name = name, content = content))


    def manifest_item (self, url, mediatype, id_ = None):
        """ Add item to manifest. """

        if id_ is None or xpath (self.manifest, "//*[@id = '%s']" % id_):
            self.item_id += 1
            id_ = 'item%d' % self.item_id
            
        self.manifest.append (
            self.opf.item (**{
                'href': url,
                'id': id_,
                'media-type': mediatype}))

        return id_


    def spine_item (self, url, mediatype, id_ = None, linear = True, first = False):
        """ Add item to spine and manifest. """
        linear = 'yes' if linear else 'no'

        if id_ and id_.startswith ('pgepubid'):
            # this is an auto-generated header id, not human-readable and probably duplicated
            # make a new one
            id_ = None
            
        id_ = self.manifest_item (url, mediatype, id_)
        
        # HACK: ADE needs cover flow as first element
        # but we don't know if we have a native coverpage until the manifest is complete
        if first:
            self.spine.insert (0, 
                self.opf.itemref (idref = id_, linear = linear))
        else:
            self.spine.append (
                self.opf.itemref (idref = id_, linear = linear))


    def manifest_item_from_parser (self, p):
        """ Add item to manifest from parser. """
        if hasattr (p, 'comment') and p.comment:
            self.manifest.append (etree.Comment (p.comment))
        return self.manifest_item (p.url, p.mediatype, p.id)
        

    def spine_item_from_parser (self, p):
        """ Add item to spine and manifest from parser. """
        if hasattr (p, 'comment') and p.comment:
            self.manifest.append (etree.Comment (p.comment))
        return self.spine_item (p.url, p.mediatype, p.id)
        

    def toc_item (self, url):
        """ Add TOC to manifest and spine. """
        self.manifest_item (url, 'application/x-dtbncx+xml', 'ncx')
        self.spine.attrib['toc'] = 'ncx'


    def pagemap_item (self, url):
        """ Add page-map to manifest and spine. """
        self.manifest_item (url, 'application/oebps-page-map+xml', 'map')
        self.spine.attrib['page-map'] = 'map'


    def metadata_item (self, dc):
        """ Build metadata from DublinCore struct.

        Example of metadata:
        
  <metadata xmlns:dcterms='http://purl.org/dc/terms/'
            xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'
            xmlns:opf='http://www.idpf.org/2007/opf'>

    <dcterms:identifier opf:scheme='URI' id='id'>http://www.gutenberg.org/ebooks/29000</dc:identifier>
    <dcterms:creator opf:file-as='Trollope, Anthony'>Anthony Trollope</dc:creator>
    <dcterms:title>The Macdermots of Ballycloran</dc:title>
    <dcterms:language xsi:type='dcterms:RFC3066'>en</dc:language>
    <dcterms:subject>Domestic fiction</dc:subject>
    <dcterms:subject>Ireland -- Fiction</dc:subject>
    <dcterms:created>1890</dcterms:created>
    <dcterms:publisher>Project Gutenberg</dc:publisher>
    <dcterms:date opf:event='publication'>2009-05-31</dc:date>
    <dcterms:date opf:event='conversion'>2009-08-26T21:11:14Z</dc:date>
    <dcterms:rights>Public domain</dc:rights>
    <dcterms:source>29000-h.htm</dc:source>

    <meta name='cover' content='item0' />
  </metadata>
    """   

        # OPF 2.0 v1.0 specifies to use the 
        # Dublin Core Metadata Element Set, Version 1.1
        # http://dublincore.org/documents/2004/12/20/dces/
        # but that has been superseded by DCMI Metadata Terms
        # http://dublincore.org/documents/dcmi-terms/
        # we use NS.dc for now but should switch to NS.dcterms later

        dcterms = ElementMaker (nsmap = self.nsmap, namespace = str (NS.dc))

        if dc.publisher:
            self.metadata.append (dcterms.publisher (dc.publisher))
        if dc.rights:
            self.metadata.append (dcterms.rights (dc.rights))

        self.metadata.append (dcterms.identifier (dc.opf_identifier, 
                { NS.opf.scheme: 'URI', 
                  'id': 'id' })) # should be NS.xml.id 

        for author in dc.authors:
            pretty_name = dc.make_pretty_name (author.name)
            if author.marcrel == 'aut' or author.marcrel == 'cre':
                self.metadata.append (dcterms.creator (
                        pretty_name, { NS.opf['file-as']: author.name }))
            else:
                self.metadata.append (dcterms.contributor (
                        pretty_name, { NS.opf.role: author.marcrel, 
                                       NS.opf['file-as']: author.name }))

        # replace newlines with /
        title = re.sub ('\s*[\r\n]+\s*', ' / ', dc.title)
        self.metadata.append (dcterms.title (title))

        for language in dc.languages:
            self.metadata.append (dcterms.language (
                    language.id, { NS.xsi.type: 'dcterms:RFC4646' }))

        for subject in dc.subjects:
            self.metadata.append (dcterms.subject (subject.subject))

        if dc.created:
            self.metadata.append (dcterms.date (
                dc.created, { NS.opf.event: 'creation'}))

        if dc.release_date:
            self.metadata.append (dcterms.date (
                    dc.release_date.isoformat (), 
                    { NS.opf.event: 'publication'}))
            
        self.metadata.append (dcterms.date (datetime.datetime.now (
                    gg.UTC ()).isoformat (), 
                                  { NS.opf.event: 'conversion'}))

        source = dc.source
        if hasattr (options.config, 'FILESDIR'):
            if source.startswith (options.config.FILESDIR):
                source = source[len (options.config.FILESDIR):]
                source = urlparse.urljoin (options.config.PGURL, source)
                
        self.metadata.append (dcterms.source (source))


    def add_coverpage (self, ocf, url):
        """ Add a coverpage for ADE and Kindle.

        The recommended cover size is 600x800 pixels (500 pixels on
        the smaller side is an absolute minimum). The cover page
        should be a color picture in JPEG format.
        
        """

        id_ = None

        # look for a manifest item with the right url
        for item in xpath (
            self.manifest,
            # cannot xpath for default namespace 
            "//*[local-name () = 'item' and starts-with (@media-type, 'image/jpeg') and @href = $url]", 
            url = url):

            id_ = item.get ('id')
            break

        # else use default cover page image
        if id_ is None:
            url = 'cover.jpg'
            mediatype = mt.jpeg
            ocf.add_bytes (url, resource_string ('epubmaker.writers', url), mediatype)
            id_ = self.manifest_item (url, mediatype)

        debug ("Adding coverpage id: %s url: %s" % (id_, url))

        # register mobipocket style
        self.meta_item ('cover', id_)
        
        # register ADE style
        href = ocf.add_image_wrapper (Writer.url2filename (url), 'Cover')
        self.spine_item (href, mt.xhtml, 'coverpage-wrapper', False, True)
        self.guide_item (href, 'cover', 'Cover')



class EpubSpider (Spider.Spider):
    """ A spider that knows about OPS mediatypes. """
    
    def is_wanted_doc (self, parser):
        """ Return True if we ought to parse this content document. """

        if parser.mediatype not in OPS_CONTENT_DOCUMENTS:
            debug ("Dropping non-ops-content %s" % parser.url)
            return False

        return Spider.Spider.is_wanted_doc (self, parser)


    def is_wanted_aux (self, parser):
        """ Return True if we ought to parse this image or aux file. """

        # debug ("Is wanted aux? %s" % parser.url)
        if parser.attribs.get ('rel') == 'coverpage':
            return True
        if Spider.Spider.is_wanted_aux (self, parser):
            return True
        return parser.mediatype not in OPS_CORE_MEDIATYPES


class Writer (writers.HTMLishWriter):
    """ Class that writes epub files. """


    def setup (self, options):
        """ Setup writer options. """

        if not options.include_mediatypes:
            options.include_mediatypes = OPS_CORE_MEDIATYPES
        self.spider = EpubSpider ()
            
        super (Writer, self).setup (options)


    @staticmethod
    def strip_pagenumbers (xhtml):
        """

        Strip dp page numbers.

        Rationale: DP implements page numbers either with float or
        with absolute positioning. Float is not supported by Kindle.
        Absolute positioning is not allowed in epub.

        If we'd leave these in, they would show up as numbers in the
        middle of the text.

        To still keep links working, we replace all page number
        contraptions we can find with empty <a>'s.

        """

        # look for elements with a class that is in STRIP_CLASSES
        
        for elem in xpath (xhtml, "//xhtml:*[@class]"):
            classes = elem.get ('class').split ()
            if STRIP_CLASSES.intersection (classes):

                # is there a class on this element that is in DP_PAGENUMBER_CLASSES ?
                pageno = len (DP_PAGENUMBER_CLASSES.intersection (classes)) > 0
                
                # save textual content
                text = gg.normalize (etree.tostring (elem,
                                                     method = "text",
                                                     encoding = unicode,
                                                     with_tail = False))
                if len (text) > 10:
                    # safeguard against removing things that are not pagenumbers
                    continue

                if not text:
                    text = elem.get ('title')

                # look for id anywhere inside element
                id_ = elem.xpath (".//@id")

                # transmogrify element into empty <a>
                tail = elem.tail
                elem.clear ()
                elem.tag = NS.xhtml.a
                if id_:
                    # some blockheaded PPers include more than
                    # one page number in one span. take the last id
                    # because the others represent empty pages.
                    elem.set ('id', id_[-1])
                if pageno:
                    # avoid conflicts with class pageno in input css files
                    # we actually don't need this class for styling 
                    # anyway because it is on an empty element
                    elem.set ('class', 'x-epubmaker-pageno')
                if text:
                    elem.set ('title', text)
                elem.tail = tail
                
                # The OPS Spec 2.0 is very clear: "Reading Systems
                # must be XML processors as defined in XML 1.1."
                # Nevertheless many browser-plugin ebook readers use
                # the HTML parsers of the browser.  But HTML parsers
                # don't grok the minimized form of empty elements.
                #
                # This will force lxml to output the non-minimized form
                # of the element.
                elem.text = ''


    @staticmethod
    def insert_root_div (xhtml):
        """ Insert a div immediately below body and move body contents
        into it.

        Rationale: We routinely turn page numbers into <a> elements.
        <a> elements are illegal as children of body, but are legal as
        children of <div>. See: `strip_page_numbers ()`

        """
        em = ElementMaker (namespace = str (NS.xhtml),
                           nsmap = { None: str (NS.xhtml) })

        for body in xpath (xhtml, "/xhtml:body"):
            div = em.div
            div.set ('id', 'pgepub-root-div')
            for child in body:
                div.append (child)
            body.append (div)
        
        
    # characters that are not widely supported
    translate_map = {
        0x2012: 0x2013,    # U+2012 FIGURE-DASH    -> U+2013 EN-DASH (ADE lacks this)
        0x2015: 0x2014,    # U+2015 HORIZONTAL BAR -> U+2014 EM-DASH (ADE lacks this)
    }

    @staticmethod
    def fix_charset (xhtml):
        """ Replace some characters that are not widely supported. """

        for node in xhtml.iter ():
            if node.text:
                node.text = unicode (node.text).translate (Writer.translate_map)
            if node.tail:
                node.tail = unicode (node.tail).translate (Writer.translate_map)
        
        
    @staticmethod
    def fix_css (sheet):
        """ Strip CSS properties and values that are not EPUB compatible. """

        for rule in sheet:
            if rule.type == rule.STYLE_RULE:
                for p in rule.style:
                    if p.name in (CSS_PROPERTIES_TO_STRIP):
                        debug ("Dropping property %s" % p.name)
                        rule.style.removeProperty (p.name)


    @staticmethod
    def fix_style_elements (xhtml):
        """ Fixup CSS style elements """

        for style in xpath (xhtml, "//xhtml:style"):
            p = parsers.CSSParser.Parser ()
            p.parse_string (style.text.encode ('utf-8'))
            p.drop_floats ()
            try:
                # pylint: disable=E1103
                style.text = p.sheet.cssText.decode ('utf-8')
            except ValueError:
                debug ("CSS:\n%s" % p.sheet.cssText)
                raise
        
        
    @staticmethod
    def strip_links (xhtml, manifest):
        """ Strip all links to images.

        This does not strip inline images, only images that are
        targets of links. EPUB does not allow that.

        """

        for link in xpath (xhtml, '//xhtml:a[@href]'):
            href = urlparse.urldefrag (link.get ('href'))[0]
            if not manifest[href] in OPS_CONTENT_DOCUMENTS:
                debug ("strip_links: Deleting <a> to non-ops-document-type: %s" % href)
                del link.attrib['href']
                continue

                
    @staticmethod
    def strip_ins (xhtml):
        """ Strip all <ins> tags.

        There's a bug in the epub validator that trips on class and
        title attributes in <ins> elements.
        
        """

        for ins in xpath (xhtml, '//xhtml:ins'):
            ins.drop_tag ()
            #if 'class' in ins.attrib:
            #    del ins.attrib['class']
            #if 'title' in ins.attrib:
            #    del ins.attrib['title']


    @staticmethod
    def strip_noepub (xhtml):
        """ Strip all <* class='x-epubmaker-drop'> tags.

        As a way to tailor your html towards epub.
        
        """

        for e in xpath (xhtml, "//xhtml:*[contains (@class, 'x-epubmaker-drop')]"):
            e.drop_tree ()


    @staticmethod
    def strip_rst_dropcaps (xhtml):
        """ Replace <img class='dropcap'> with <span class='dropcap'>.

        """

        for e in xpath (xhtml, "//xhtml:img[@class ='dropcap']"):
            e.tag = NS.xhtml.span
            e.text = e.get ('alt', '')


    @staticmethod
    def reflow_pre (xhtml):
        """ make <pre> reflowable.
        
        This helps a lot with readers like Sony's that cannot
        scroll horizontally.

        """

        def nbsp (matchobj):
            return (' ' * (len (matchobj.group (0)) - 1)) + ' '

        for pre in xpath (xhtml, "//xhtml:pre"):
            # white-space: pre-wrap would do fine
            # but it is not supported by OEB
            try:
                pre.tag = NS.xhtml.div
                writers.HTMLishWriter.add_class (pre, 'pgmonospaced')
                m = parsers.RE_GUTENBERG.search (pre.text)
                if (m):
                    writers.HTMLishWriter.add_class (pre, 'pgheader')

                tail = pre.tail
                s = etree.tostring (pre, with_tail=False)
                s = s.replace ('>\n', '>')      # eliminate that empty first line
                s = s.replace ('\n', '<br/>')
                s = re.sub ('  +', nbsp, s)
                div = etree.fromstring (s)
                div.tail = tail
                
                pre.getparent ().replace (pre, div)
                
            except etree.XMLSyntaxError, what:
                exception ("%s\n%s" % (s, what))
                raise


    @staticmethod
    def single_child (e):
        """ Resturn true if node contains a single child element and nothing else. """
        p = e.getparent ()
        return (len (p) == 1 and
                (p.text is None or p.text.isspace ()) and
                (e.tail is None or e.tail.isspace ())
                )

                
    @staticmethod
    def url2filename (url):
        """ Generate a filename for this url.

        From the wget docs:
        
            When 'unix' is specified, Wget escapes the character '/'
            and the control characters in the ranges 0-31 and 128-159.
            This is the default on Unix-like operating systems.

            When 'windows' is given, Wget escapes the characters '\',
            '|', '/', ':', '?', '\"', '*', '<', '>', and the control
            characters in the ranges 0-31 and 128-159.  In addition to
            this, Wget in Windows mode uses '+' instead of ':' to
            separate host and port in local file names, and uses '@'
            instead of '?' to separate the query portion of the file
            name from the rest.  Therefore, a URL that would be saved
            as 'www.xemacs.org:4300/search.pl?input=blah' in Unix mode
            would be saved as
            'www.xemacs.org+4300/search.pl@input=blah' in Windows
            mode.  This mode is the default on Windows.
        
            If you specify `nocontrol', then the escaping of the
            control characters is also switched off. This option may
            make sense when you are downloading URLs whose names
            contain UTF-8 characters, on a system which can save and
            display filenames in UTF-8 (some possible byte values used
            in UTF-8 byte sequences fall in the range of values
            designated by Wget as 'controls').

        For debugging we want to keep a filename resembling the url we
        downloaded from instead of using a counter.
        
        Also, we want the user to be able to unzip the epub. Thus we
        must generate filenames that can be understood by the most
        limited OS around (aka. Windows).


        """

        def escape (matchobj):
            """ Escape a char. """
            return '@%x' % ord (matchobj.group (0))

        url = urllib.unquote (url)
        url = re.sub ('^.*?://', '', url)
        url = os.path.normpath (url)
        url = url.replace ('/', '@')
        url = re.sub (u'[\|/:?"*<>\u0000-\u001F]', escape, url)

        # url = url.translate (string.maketrans (':?', '+@')) # windows stupidity

        return url


    @staticmethod
    def rescale_into (dimen, max_dimen):
        """ Scale down dimen to fit into max_dimen. """
        scale = 1.0
        if dimen[0]:
            scale = min (scale, max_dimen[0] / float (dimen[0])) 
        if dimen[1]:
            scale = min (scale, max_dimen[1] / float (dimen[1]))

        if scale < 1.0:
            dimen = (int (dimen[0] * scale) if dimen[0] else None,
                     int (dimen[1] * scale) if dimen[1] else None)

        return dimen
        
        
    @staticmethod    
    def fix_html_image_dimensions (xhtml):
        """

        Remove all width and height that is not specified in '%'.

        """

        for img in xpath (xhtml, '//xhtml:img'):
            a = img.attrib

            if ('%' in a.get ('width', '%') and '%' in a.get ('height', '%')):
                continue

            if 'width' in a:
                del a['width']
            if 'height' in a:
                del a['height']


    def remove_coverpage (self, xhtml, url):
        """ Remove coverpage from flow.

        EPUB readers will display the coverpage from the manifest and
        if we don't remove it from flow it will be displayed twice.

        """
        for img in xpath (xhtml, '//xhtml:img[@src = $url]', url = url):
            debug ("remove_coverpage: dropping <img> %s from flow" % url)
            img.drop_tree ()
            return # only the first one though


    def shipout (self, parsers, ncx):
        """ Build the zip file. """

        try:
            ocf = OEBPSContainer (
                os.path.join (self.options.outputdir, self.options.outputfile),
                ('%d/' % self.options.ebook if self.options.ebook else None))

            opf = ContentOPF ()

            opf.metadata_item (self.options.dc)

            # write out parsers

            for p in parsers:
                try:
                    ocf.add_bytes (self.url2filename (p.url), p.serialize (), p.mediatype)
                    if p.mediatype == 'application/xhtml+xml':
                        opf.spine_item_from_parser (p)
                    else:
                        opf.manifest_item_from_parser (p)
                except StandardError, what:
                    error ("Could not process file %s: %s" % (p.url, what))

            # toc

            for t in ncx.toc:
                if t[1].lower ().strip (' .') in TOC_HEADERS:
                    opf.guide_item (t[0], 'toc', t[1])
                    break
                    
            opf.toc_item ('toc.ncx')
            ocf.add_unicode ('toc.ncx', unicode (ncx))

            if options.coverpage_url:
                opf.add_coverpage (ocf, options.coverpage_url)
            
            # Adobe page-map

            # opf.pagemap_item ('page-map.xml')
            # ocf.add_unicode ('page-map.xml', unicode (AdobePageMap (ncx)))
            
            # content.opf

            # debug (etree.tostring (opf.manifest, encoding=unicode, pretty_print=True))
            
            opf.rewrite_links (self.url2filename)
            ocf.add_unicode ('content.opf', unicode (opf))

            ocf.commit ()

        except StandardError, what:
            exception ("Error building Epub: %s" % what)
            ocf.rollback ()
            raise


    def validate (self):
        """ Validate generated epub using external tools. """
        
        debug ("Validating %s ..." % self.options.outputfile)

        filename = os.path.join (self.options.outputdir, 
                                 self.options.outputfile)

        for validator in (options.config.EPUB_VALIDATOR, options.config.EPUB_PREFLIGHT):
            if validator is not None:
                params = validator.split () + [filename]
                checker = subprocess.Popen (params,
                                    stdin = subprocess.PIPE, 
                                    stdout = subprocess.PIPE, 
                                    stderr = subprocess.PIPE)

                (dummy_stdout, stderr) = checker.communicate ()
                if (stderr):
                    error (stderr)
                    return 1
                    #raise AssertionError (
                    #    "%s does not validate." % self.options.outputfile)

        debug ("%s validates ok." % self.options.outputfile)
        return 0
    

    def build (self):
        """ Build epub """

        ncx = TocNCX (self.options.dc)
        parsers = []
        css_count = 0

        # add CSS parser
        self.add_external_css (None, PRIVATE_CSS, 'pgepub.css')

        try:
            chunker = HTMLChunker.HTMLChunker ()
            
            # do images first as we need the new dimensions later
            for p in self.spider.parsers:
                if hasattr (p, 'resize_image'):
                    if self.options.maintype == 'kindle':
                        if p.url == options.coverpage_url:
                            np = p.resize_image (MAX_IMAGE_SIZE_KINDLE, MAX_COVER_DIMEN_KINDLE, 'jpeg')
                            np.id = p.attribs.get ('id', 'coverpage')
                            id_coverpage = np.id
                        else:
                            np = p.resize_image (MAX_IMAGE_SIZE_KINDLE, MAX_IMAGE_DIMEN_KINDLE)
                            np.id = p.attribs.get ('id')
                    else:
                        if p.attribs.get ('rel') == 'coverpage':
                            np = p.resize_image (MAX_IMAGE_SIZE, MAX_COVER_DIMEN)
                            np.id = p.attribs.get ('id', 'coverpage')
                            id_coverpage = np.id
                        else:
                            np = p.resize_image (MAX_IMAGE_SIZE, MAX_IMAGE_DIMEN)
                            np.id = p.attribs.get ('id')
                    parsers.append (np)

            for p in self.spider.parsers:
                if p.mediatype in OPS_CONTENT_DOCUMENTS:
                    debug ("URL: %s" % p.url)

                    if hasattr (p, 'rst2epub2'):
                        # RST parser
                        # if self.options.maintype == 'kindle':
                        #     xhtml = p.rst2kindle ()
                        # else:
                        xhtml = p.rst2epub2 ()
                        
                        if self.options.verbose >= 2:
                            # write html to disk for debugging
                            debugfilename = os.path.join (self.options.outputdir,
                                                          self.options.outputfile)
                            debugfilename = os.path.splitext (debugfilename)[0] + '.' + \
                                self.options.maintype + '.debug.html'
                            with open (debugfilename, 'w') as fp:
                                fp.write (etree.tostring (xhtml, encoding = 'utf-8'))

                    else:
                        # make a copy so we can mess around
                        p.parse ()
                        xhtml = copy.deepcopy (p.xhtml)
                        
                    self.strip_pagenumbers (xhtml)

                    # build up TOC
                    # has side effects on xhtml
                    ncx.toc += p.make_toc (xhtml)

                    self.insert_root_div (xhtml)
                    self.fix_charset (xhtml)
                    self.fix_style_elements (xhtml)
                    self.reflow_pre (xhtml)

                    # strip all links to items not in manifest
                    p.strip_links (xhtml, self.spider.dict_urls_mediatypes ())
                    self.strip_links (xhtml, self.spider.dict_urls_mediatypes ())

                    # FIXME: remove strip_ins when epubcheck is fixed
                    # epubcheck 1.0.4 is broken
                    # self.strip_ins (xhtml)
                    self.strip_noepub (xhtml)
                    # self.strip_rst_dropcaps (xhtml)

                    self.fix_html_image_dimensions (xhtml)
                    if options.coverpage_url:
                        self.remove_coverpage (xhtml, options.coverpage_url)

                    # externalize and fix CSS
                    for style in xpath (xhtml, '//xhtml:style'):
                        self.add_external_css (
                            xhtml, style.text, "%d.css" % css_count)
                        css_count += 1
                        style.drop_tree ()
                        
                    self.add_external_css (xhtml, None, 'pgepub.css')
                    
                    self.add_meta_generator (xhtml)

                    debug ("Splitting %s ..." % p.url)
                    chunker.next_id = 0
                    chunker.split (xhtml, p.url)

            for p in self.spider.parsers:
                if hasattr (p, 'sheet'):
                    self.fix_css (p.sheet)
                    p.rewrite_links (self.url2filename)
                    parsers.append (p)
                        
            # after splitting html into chunks we have to rewrite all
            # internal links in HTML
            chunker.rewrite_internal_links ()
            # also in the TOC
            if not ncx.toc:
                ncx.toc.append ([self.spider.parsers[0].url, 'Start', 1])
            chunker.rewrite_internal_links_toc (ncx.toc)

            # make absolute links zip-filename-compatible
            chunker.rewrite_links (self.url2filename)
            ncx.rewrite_links (self.url2filename)

            # do away with chunker, copy chunks into new parsers
            for chunk in chunker.chunks:
                # these parsers never actually parsed anything
                # we use them to just hold our data
                p = ParserFactory.ParserFactory.get ('application/xhtml+xml')
                p.mediatype = 'application/xhtml+xml'
                p.comment = chunk['comment']
                p.url = chunk['name']
                p.xhtml = chunk['chunk']
                p.id = chunk['id']
                parsers.append (p)

            self.shipout (parsers, ncx)

        except StandardError, what:
            exception ("Error building Epub: %s" % what)
            raise


