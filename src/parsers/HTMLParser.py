#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

HTMLParser.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

"""

import re
import subprocess
import urllib
import urlparse

import lxml.html
from lxml import etree
# import tidy

from epubmaker.lib.GutenbergGlobals import NS, xpath
from epubmaker.lib.Logger import info, debug, warn, error
from epubmaker.lib.MediaTypes import mediatypes as mt

from epubmaker import parsers
from epubmaker.parsers import HTMLParserBase

mediatypes = ('text/html', mt.xhtml)

RE_XMLDECL = re.compile ('<\?xml[^?]+\?>\s*')

DEPRECATED = { 'align':      """caption applet iframe img input object legend
                             table hr div h1 h2 h3 h4 h5 h6 p""",
               'alink':      'body',
               'alt':        'applet',
               'archive':    'applet',
               'background': 'body',
               'bgcolor':    '*',
               'border':     'img object',
               'clear':      'br',
               'code':       'applet',
               'codebase':   'applet',
               'color':      '*',
               'compact':    '*',
               'face':       '*',
               'height':     'td th applet',
               'hspace':     '*',
               'language':   'script',
               'link':       'body',
               'name':       'applet',
               'noshade':    'hr',
               'nowrap':     '*',
               'object':     'applet',
               'prompt':     'isindex',
               'size':       'hr font basefont',
               'start':      'ol',
               'text':       'body',
               'type':       'li ol ul',
               'value':      'li',
               'version':    'html',
               'vlink':      'body',
               'vspace':     '*',
               'width':      'hr td th applet pre',
               }


class Parser (HTMLParserBase):
    """ Parse a HTML Text

    and convert it to xhtml suitable for ePub packaging.

    """

    @staticmethod
    def _fix_id (id_):
        """ Fix more common mistakes in ids.

        xml:id cannot start with digit, very common in pg.

        """

        if not parsers.RE_XML_NAME.match (id_):
            id_ = 'id_' + id_

        # debug ("_fix_id: id = %s" % id_)
        return id_


    def _fix_internal_frag (self, id_):
        """ Fix more common mistakes in ids. """

        # This is a big mess because href attributes must be quoted,
        # but id attributes must not be quoted.  Some HTML in PG
        # quotes ids in a misguided attempt to make id and href look
        # the same.  But '%' is invalid in xml ids.
        #
        # See HTML 4.01 spec section B.2.

        if '%' in id_:
            id_ = urllib.unquote (id_)
            try:
                id_ = id_.decode ('utf-8')
            except UnicodeError:
                try:
                    id_ = id_.decode (self.encoding)
                except UnicodeError:
                    pass # we tried

        # xml:id cannot start with digit
        # very common in pg

        if not parsers.RE_XML_NAME.match (id_):
            id_ = 'id_' + id_

        if not parsers.RE_XML_NAME.match (id_):
            # still invalid ... we tried
            return None

        # debug ("_fix_internal_frag: frag = %s" % id_)
        return id_


    # @staticmethod
    # def tidylib (html):
    #     """ Pipe html thru w3c tidylib. """

    #     html = parsers.RE_RESTRICTED.sub ('', html)
    #     html = RE_XMLDECL.sub ('', html)
    #     html = parsers.RE_HTML_CHARSET.sub ('; charset=utf-8', html)

    #     options = {
    #         "clean": 1,
    #         "wrap":  0,
    #         "output_xhtml":     1,
    #         "numeric_entities": 1,
    #         "merge_divs":       0, # keep poetry indentation
    #         "merge_spans":      0,
    #         "add_xml_decl":     0,
    #         "doctype":          "strict",
    #         "anchor_as_name":   0,
    #         "enclose_text":     1,
    #         }

    #     try:
    #         html = tidy.parseString (html.encode ('utf-8'))
    #     except TidyLibError, what:
    #         error ("Tidy: %s" % what)
    #         raise

    #     return html


    @staticmethod
    def tidy (html):
        """ Pipe html thru w3c tidy. """

        html = parsers.RE_RESTRICTED.sub ('', html)
        html = RE_XMLDECL.sub ('', html)
        html = parsers.RE_HTML_CHARSET.sub ('; charset=utf-8', html)

        # convert to xhtml
        tidy = subprocess.Popen (
            ["tidy",
             "-utf8",
             "-clean",
             "--wrap",             "0",
             # "--drop-font-tags",   "y",
             # "--drop-proprietary-attributes", "y",
             # "--add-xml-space",    "y",
             "--output-xhtml",     "y",
             "--numeric-entities", "y",
             "--merge-divs",       "n", # keep poetry indentation
             "--merge-spans",      "n",
             "--add-xml-decl",     "n",
             "--doctype",          "strict",
             "--anchor-as-name",   "n",
             "--enclose-text",     "y" ],

            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)

        # print (html.encode ('utf-8'))
        # sys.exit ()

        (html, stderr) = tidy.communicate (html.encode ('utf-8'))

        regex = re.compile ('(Info:|Warning:|Error:)\s*', re.I)

        # pylint: disable=E1103
        msg = stderr.rstrip ()
        for line in msg.splitlines ():
            match = regex.search (line)
            if match:
                sline = regex.sub ("", line)
                g = match.group (1).lower ()
                if g == 'info:':
                    info ("tidy: %s" % sline)
                elif g == 'warning:':
                    warn ("tidy: %s" % sline)
                elif g == 'error:':
                    error ("tidy: %s" % sline)
                else:
                    error (line)

        if tidy.returncode == 2:
            raise ValueError, stderr

        return html.decode ('utf-8')


    def find_coverpage (self):
        """ Search coverpage and put url into <link rel="coverpage" >.

        First look for an image with id of 'coverpage', then for an
        image with 'cover' in the url, then with 'title' in the url.

        """
        for head in xpath (self.xhtml, 'xhtml:head'):
            for dummy_link in xpath (head, 'xhtml:link[@rel = "coverpage"]'):
                # already there
                return

            covers = (xpath (self.xhtml, '//xhtml:img[@id = "coverpage"]') or
                      xpath (self.xhtml, '//xhtml:img[contains (@src, "cover")]') or
                      xpath (self.xhtml, '//xhtml:img[contains (@src, "title")]'))
            if not covers:
                return

            href = covers[0].get ('src')
            # FIXME: enforce minimum size
            head.append (etree.Element (NS.xhtml.link, rel = 'coverpage', href = href))
            return href


    def _fix_anchors (self):
        """ Move name to id and fix hrefs and ids. """

        # move anchor name to id
        # 'id' values are more strict than 'name' values
        # try to fix ill-formed ids

        seen_ids = set ()

        for anchor in (xpath (self.xhtml, "//xhtml:a[@name]") +
                       xpath (self.xhtml, "//xhtml:*[@id]")):
            id_ = anchor.get ('id') or anchor.get ('name')

            if 'name' in anchor.attrib:
                del anchor.attrib['name']
            if 'id' in anchor.attrib:
                del anchor.attrib['id']
            if NS.xml.id in anchor.attrib:
                del anchor.attrib[NS.xml.id]

            id_ = self._fix_id (id_)

            if not parsers.RE_XML_NAME.match (id_):
                error ("Dropping ill-formed id '%s' in %s" % (id_, self.url))
                continue

            # well-formed id
            if id_ in seen_ids:
                error ("Dropping duplicate id '%s' in %s" % (id_, self.url))
                continue

            seen_ids.add (id_)
            anchor.set ('id', id_)


        # try to fix bogus fragment ids
        # 1. fragments point to xml:id, so must be well-formed ids
        # 2. the ids they point to must exist

        for link in xpath (self.xhtml, "//xhtml:*[@href]"):
            href = link.get ('href')
            hre, frag = urlparse.urldefrag (href)
            if frag:
                frag = self._fix_internal_frag (frag)

                if not frag:
                    # non-recoverable ill-formed frag
                    del link.attrib['href']
                    self.add_class (link, 'pgkilled')
                    error ('Dropping ill-formed frag in %s' % href)
                    continue

                # well-formed frag
                if hre:
                    # we have url + frag
                    link.set ('href', "%s#%s" % (hre, urllib.quote (frag.encode ('utf-8'))))
                    self.add_class (link, 'pgexternal')
                elif frag in seen_ids:
                    # we have only frag
                    link.set ('href', "#%s" % urllib.quote (frag.encode ('utf-8')))
                    self.add_class (link, 'pginternal')
                else:
                    del link.attrib['href']
                    self.add_class (link, 'pgkilled')
                    error ("Dropping frag to non-existing id in %s" % href)


    def _to_xhtml11 (self):
        """ Make vanilla xhtml more conform to xhtml 1.1 """

        # Change content-type meta to application/xhtml+xml.
        for meta in xpath (self.xhtml, "/xhtml:html/xhtml:head/xhtml:meta[@http-equiv]"):
            if meta.get ('http-equiv').lower () == 'content-type':
                meta.set ('content', mt.xhtml + '; charset=utf-8')

        # drop javascript

        for script in xpath (self.xhtml, "//xhtml:script"):
            script.drop_tree ()

        # drop form

        for form in xpath (self.xhtml, "//xhtml:form"):
            form.drop_tree ()

        # blockquotes

        for bq in xpath (self.xhtml, "//xhtml:blockquote"):
            # no naked text allowed in <blockquote>
            div = etree.Element (NS.xhtml.div)
            for child in bq:
                div.append (child)
            div.text = bq.text
            bq.text = None
            bq.append (div)
            # lxml.html.defs.block_tags

        # insert tbody

        for table in xpath (self.xhtml, "//xhtml:table[xhtml:tr]"):
            # no naked <tr> allowed in <table>
            tbody = etree.Element (NS.xhtml.tbody)
            for tr in table:
                if tr.tag == NS.xhtml.tr:
                    tbody.append (tr)
            table.append (tbody)

        # move lang to xml:lang

        for elem in xpath (self.xhtml, "//xhtml:*[@lang]"):
            # bug in lxml 2.2.2: sometimes deletes wrong element
            # so we delete both and reset the right one
            lang = elem.get ('lang')
            try:
                del elem.attrib[NS.xml.lang]
            except KeyError:
                pass
            del elem.attrib['lang']
            elem.set (NS.xml.lang, lang)

        # strip deprecated attributes

        for a, t in DEPRECATED.items ():
            for tag in t.split ():
                for elem in xpath (self.xhtml, "//xhtml:%s[@%s]" % (tag, a)):
                    del elem.attrib[a]

        # strip empty class attributes

        for elem in xpath (self.xhtml,
            "//xhtml:*[@class and normalize-space (@class) = '']"):
            del elem.attrib['class']

        # strip bogus header markup by Joe L.
        for elem in xpath (self.xhtml, "//xhtml:h1"):
            if elem.text and elem.text.startswith ("The Project Gutenberg eBook"):
                elem.tag = NS.xhtml.p
        for elem in xpath (self.xhtml, "//xhtml:h3"):
            if elem.text and elem.text.startswith ("E-text prepared by"):
                elem.tag = NS.xhtml.p


    def __parse (self, html):
        # remove xml decl and doctype, we will add the correct one before serializing
        # html = re.compile ('^.*<html ', re.I | re.S).sub ('<html ', html)
        # FIXME: do not remove doctype because we need it to load the dtd

        # remove xml declaration because of parser error: "Unicode
        # strings with encoding declaration are not supported. Please
        # use bytes input or XML fragments without declaration."
        re_xml_decl = re.compile (r'^<\?xml.*?\?>', re.S)
        html = re_xml_decl.sub ('', html)
        try:
            return etree.fromstring (
                html,
                lxml.html.XHTMLParser (),
                base_url = self.url)
        except etree.ParseError, what:
            # cannot try HTML parser because we depend on correct xhtml namespace
            error ("etree.fromstring says: %s" % what)
            m = re.search (r'line\s(\d+),', str (what))
            if m:
                lineno = int (m.group (1))
                error ("Line %d: %s" % (lineno, html.splitlines ()[lineno - 1]))
            raise


    def pre_parse (self):
        """ Pre-parse a html ebook. Does a full parse because a
        lightweight parse would be almost as much work. """

        # cache
        if self.xhtml is not None:
            return

        debug ("HTMLParser.pre_parse () ...")

        html = self.unicode_content ()

        if html.startswith ('<?xml'):
            # Try a naive parse. This might fail because of errors in
            # the html or because we have no dtd loaded.  We do not
            # load dtds because that makes us dependent on network and
            # the w3c site being up.  Having all users of epubmaker
            # install local dtds is unrealistic.
            try:
                self.xhtml = self.__parse (html)
            except etree.ParseError:
                pass

        if self.xhtml is None:
            # previous parse failed, try tidy
            info ("Running html thru tidy.")
            html = self.tidy (html)
            self.xhtml = self.__parse (html)     # let exception bubble up

        self._fix_anchors () # needs relative paths
        self.xhtml.make_links_absolute (base_url = self.url)
        self.find_coverpage ()

        self._to_xhtml11 ()

        debug ("Done parsing %s" % self.url)


    def parse (self):
        """ Fully parse a html ebook. """

        debug ("HTMLParser.parse () ...")

        self.pre_parse ()
