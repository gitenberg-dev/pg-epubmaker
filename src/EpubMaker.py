#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

EpubMaker.py

Copyright 2009-2011 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Stand-alone application to build epub out of html or rst.

"""


from __future__ import with_statement

import sys
import os.path
import re
import optparse
import hashlib
import mimetypes

from epubmaker.lib.GutenbergGlobals import Struct, DCIMT, SkipOutputFormat
import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.Logger import debug, exception
from epubmaker.lib import Logger, DublinCore

from epubmaker import ParserFactory
from epubmaker import WriterFactory
from epubmaker.packagers import PackagerFactory
from epubmaker import CommonOptions

from epubmaker.Version import VERSION

def null_translation (s):
    """ Translate into same language. :-) """
    return s

TXT_FORMATS    = 'txt.utf-8 txt.iso-8859-1 txt.us-ascii'.split ()
HTML_FORMATS   = 'html.noimages html.images'.split ()
EPUB_FORMATS   = 'epub.noimages epub.images'.split ()
KINDLE_FORMATS = 'kindle.noimages kindle.images'.split ()
PDF_FORMATS    = 'pdf.noimages pdf.images'.split ()
RST_FORMATS    = 'rst.gen'.split ()
ALL_FORMATS    = HTML_FORMATS + EPUB_FORMATS + KINDLE_FORMATS + PDF_FORMATS + TXT_FORMATS + RST_FORMATS

DEPENDENCIES = (
    ('all',    ALL_FORMATS),
    ('html',   HTML_FORMATS), 
    ('epub',   EPUB_FORMATS),
    ('kindle', KINDLE_FORMATS), 
    ('pdf',    PDF_FORMATS),
    ('txt',    TXT_FORMATS), 
    ('rst',    RST_FORMATS), 
    )

FILENAMES = {
    'html.noimages':    '{id}-noimages-h.html',
    'html.images':      '{id}-h.html',

    'epub.noimages':    '{id}-epub.epub',
    'epub.images':      '{id}-images-epub.epub',

    'kindle.noimages':  '{id}-kindle.mobi',
    'kindle.images':    '{id}-images-kindle.mobi',

    'pdf.noimages':     '{id}-pdf.pdf',
    'pdf.images':       '{id}-images-pdf.pdf',

    'txt.utf-8':        '{id}-0.txt',
    'txt.iso-8859-1':   '{id}-8.txt',
    'txt.us-ascii':     '{id}.txt',

    'rst.gen':          '{id}-rst.rst',

    'picsdir.noimages': '{id}-noimages.picsdir',   # do we need this ?
    'picsdir.images':   '{id}-images.picsdir',     # do we need this ?
    }

def make_output_filename (dc, type_):
    if dc.project_gutenberg_id:
        # PG book: use PG naming convention
        return FILENAMES[type_].format (id = dc.project_gutenberg_id)
    else:
        # not a PG ebook
        return FILENAMES[type_].format (id = gg.string_to_filename (dc.title)[:65])

def main ():
    """ Main program. """

    op = optparse.OptionParser (usage = "usage: %prog [options] url", 
                                version = "EpubMaker version %s" % VERSION)

    CommonOptions.add_common_options (op)

    op.add_option (
        "--make",
        dest    = "types",
        choices = [x for x, y in DEPENDENCIES] + ALL_FORMATS,
        default = [],
        action  = 'append',
        help    = ("output type [%s] (default: all)"
                   % ' | '.join ([x for x, y in DEPENDENCIES] + ALL_FORMATS)))

    op.add_option (
        "--max-depth",
        metavar = "LEVELS",
        dest    = "max_depth",
        type    = "int",
        default = 1,
        help    = "go how many levels deep while recursively retrieving pages. (0 == infinite)")

    op.add_option (
        "--include",
        metavar = "GLOB",
        dest    = "include_argument", 
        default = [],
        action  = "append",
        help    = "include this url (use globs, repeat for more urls)")

    op.add_option (
        "--exclude",
        metavar = "GLOB",
        dest    = "exclude", 
        default = [],
        action  = "append",
        help    = "exclude this url (use globs, repeat for more urls)")

    op.add_option (
        "--include-mediatype",
        metavar = "GLOB/GLOB",
        dest    = "include_mediatypes_argument", 
        default = ['text/*', 'application/xhtml+xml'],
        action  = "append",
        help    = "include this mediatype (use globs, repeat for more mediatypes, eg. 'image/*')")

    op.add_option (
        "--exclude-mediatype",
        metavar = "GLOB/GLOB",
        dest    = "exclude_mediatypes", 
        default = [],
        action  = "append",
        help    = "exclude this mediatype (use globs, repeat for more mediatypes)")

    op.add_option (
        "--rewrite",
        metavar = "from>to",
        dest    = "rewrite", 
        default = [],
        action  = "append",
        help    = "rewrite url eg. 'http://www.example.org/>http://www.example.org/index.html'")

    op.add_option (
        "--title",
        dest    = "title", 
        default = None,
        help    = "ebook title (default: from meta)")

    op.add_option (
        "--author",
        dest    = "author", 
        default = None,
        help    = "author (default: from meta)")

    op.add_option (
        "--ebook",
        dest    = "ebook", 
        type    = "int",
        default = 0,
        help    = "ebook no. (default: from meta)")

    op.add_option (
        "--input-encoding",
        dest    = "inputencoding", 
        default = None,
        help    = "input encoding (default: from meta)")

    op.add_option (
        "--output-dir",
        dest    = "outputdir", 
        default = "./",
        help    = "output directory (default: ./)")

    op.add_option (
        "--output-file",
        dest    = "outputfile", 
        default = None,
        help    = "output file (default: <title>.epub)")

    op.add_option (
        "--packager",
        dest    = "packager",
        choices = ['none', 'ww'],
        default = "none",
        help    = "packager type [none | ww] (default: none)")

    op.add_option (
        "--mediatype-from-extension",
        dest    = "mediatype_from_extension",
        action  = "store_true",
        default = False,
        help    = "get mediatype from url extension instead of http response")

    options, args = CommonOptions.parse_args (op, {}, {
        'proxies': None,
        'bibrec': 'http://www.gutenberg.org/ebooks/',
        'xelatex': 'xelatex',
        'mobigen': 'kindlegen',
        'groff': 'groff',
        'rhyming_dict': None,
        } )

    if not args:
        op.error ("please specify which file to convert")

    import __builtin__
    __builtin__.options = options
    __builtin__._ = null_translation

    Logger.set_log_level (options.verbose)        

    options.types = options.types or ['all']
    for opt, formats in DEPENDENCIES:
        if opt in options.types:
            options.types.remove (opt)
            options.types += formats

    if set (options.types).intersection (('html.images', 'pdf.images', 'rst.gen')):
        options.types.insert (0, 'picsdir.images')
    if set (options.types).intersection (('html.noimages', 'pdf.noimages')):
        options.types.insert (0, 'picsdir.noimages')
    if set (options.types).intersection (('kindle.images', )):
        options.types.insert (0, 'epub.images')
    if set (options.types).intersection (('kindle.noimages', )):
        options.types.insert (0, 'epub.noimages')
        
        
    debug ("Building types: %s" % ' '.join (options.types))

    ParserFactory.load_parsers ()
    WriterFactory.load_writers ()

    packager_factory = None
    if options.packager != 'none':
        packager_factory = PackagerFactory (options.packager)
        packager_factory.load ()

    for url in args:

        if options.include_argument:
            options.include = options.include_argument[:]
        else:
            options.include = [ os.path.dirname (url) + '/*' ]
            
        # try to get metadata

        options.candidate = Struct ()
        options.candidate.filename = url
        options.candidate.mediatype = str (DCIMT (
            mimetypes.types_map[os.path.splitext (url)[1]], options.inputencoding))

        options.include_mediatypes = options.include_mediatypes_argument[:]
        options.want_images = False
        options.coverpage_url = None

        parser = ParserFactory.ParserFactory.create (options.candidate.filename, {})

        dc = None

        try:
            dc = DublinCore.GutenbergDublinCore ()

            # try for rst header
            dc.load_from_rstheader (parser.unicode_content ())

            if dc.project_gutenberg_id == 0:
                # try for Project Gutenberg header
                dc.load_from_parser (parser)

        except (ValueError, TypeError):
            # use standard HTML header
            dc = DublinCore.DublinCore ()
            dc.load_from_parser (parser)
            dc.source = url

        dc.source = url

        if options.title:
            dc.title = options.title
        if not dc.title:
            dc.title = 'NA'

        if options.author:
            dc.add_author (options.author, 'cre')
        if not dc.authors:
            dc.add_author ('NA', 'cre')

        if options.ebook:
            dc.project_gutenberg_id = options.ebook

        if dc.project_gutenberg_id:
            dc.opf_identifier = ('http://www.gutenberg.org/ebooks/%d' % dc.project_gutenberg_id)
        else:
            dc.opf_identifier = ('urn:mybooks:%s' %
                                 hashlib.md5 (url.encode ('utf-8')).hexdigest ())

        if not dc.languages:
            # we *need* a language to build a valid epub, so just make one up
            dc.add_lang_id ('en')

        aux_file_list = []
        
        for type_ in options.types:
            debug ('=== Building %s ===' % type_)
            maintype, subtype = os.path.splitext (type_)

            try:
                writer = WriterFactory.create (maintype)
                writer.setup (options)
                options.type = type_
                options.maintype = maintype
                options.subtype = subtype
                options.want_images = False

                options.include_mediatypes = options.include_mediatypes_argument[:]
                if subtype == '.images':
                    options.include_mediatypes.append ('image/*')
                    options.want_images = True
                else:
                    # This is the mediatype of the 'broken' image.
                    options.include_mediatypes.append ('image/png;type=resource')

                writer.parse (options)

                if maintype in ('html', ):
                    # list of images for packager
                    aux_file_list[:] = writer.get_aux_file_list ()

                options.dc = dc
                options.outputfile = make_output_filename (dc, type_)

                if maintype == 'kindle':
                    options.epub_filename = make_output_filename (dc, 'epub' + subtype)

                writer.build ()

                if options.validate:
                    writer.validate ()

                if packager_factory:
                    try:
                        packager = packager_factory.create (type_)
                        packager.setup (options)
                        packager.package (aux_file_list)
                    except KeyError:
                        # no such packager
                        pass

                options.outputfile = None

            except SkipOutputFormat:
                continue
            
            except StandardError, what:
                exception ("%s" % what)

        if options.packager == 'ww':
            try:
                packager = packager_factory.create ('push')
                options.outputfile = '%d-final.zip' % (dc.project_gutenberg_id)
                packager.setup (options)
                packager.package (aux_file_list)
            except KeyError:
                # no such packager
                pass

    sys.exit (0)

if __name__ == "__main__":
    main ()



