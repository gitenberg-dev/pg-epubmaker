#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""
MediaTypes.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Media Types Lists

"""

import mimetypes

mimetypes.init ()

# overrides

mimetypes.types_map['.htm']     = 'application/xhtml+xml'
mimetypes.types_map['.html']    = 'application/xhtml+xml'
mimetypes.types_map['.xhtml']   = 'application/xhtml+xml'
mimetypes.types_map['.mobile']  = 'application/xhtml+xml'
mimetypes.types_map['.ncx']     = 'application/x-dtbncx+xml'
mimetypes.types_map['.pt']      = 'application/vnd.adobe-page-template+xml'
mimetypes.types_map['.epub']    = 'application/epub+zip'
mimetypes.types_map['.mobi']    = 'application/x-mobipocket-ebook'
mimetypes.types_map['.pdf']     = 'application/pdf'
mimetypes.types_map['.plucker'] = 'application/prs.plucker'
mimetypes.types_map['.qioo']    = 'application/x-qioo-ebook'
mimetypes.types_map['.jar']     = 'application/java-archive'
mimetypes.types_map['.rss']     = 'application/rss+xml'
mimetypes.types_map['.atom']    = 'application/atom+xml'
mimetypes.types_map['.opds']    = 'application/atom+xml'
mimetypes.types_map['.stanza']  = 'application/atom+xml'
mimetypes.types_map['.wap']     = 'application/vnd.wap.xhtml+xml'
mimetypes.types_map['.json']    = 'application/x-suggestions+json'
mimetypes.types_map['.rst']     = 'text/x-rst'
mimetypes.types_map['.png']     = 'image/png'  # Windows XP thinks this is image/x-png
mimetypes.types_map['.jpg']     = 'image/jpeg' # Windows XP thinks this is image/pjpeg
mimetypes.types_map['.jpeg']    = 'image/jpeg' # Windows XP thinks this is image/pjpeg

TEXT_MEDIATYPES = set ( (
    'application/xhtml+xml',
    'application/xml',
    'text/html',
    'text/plain',
) )

IMAGE_MEDIATYPES = set ( (
    'image/gif',
    'image/jpeg',
    'image/png',
) )

AUX_MEDIATYPES = set ( (
    'text/css',
) )

class MediatypesLookup (object):
    """ Quick mediatype lookup

    ns = MediatypesLookup ()
    >>> ns.epub
    'application/atom+xml'
    >>> ns['mobi']
    'application/x-mobipocket-ebook'

    """

    def __getitem__ (self, local):
        return mimetypes.types_map['.' + local]

    def __getattr__ (self, local):
        return mimetypes.types_map['.' + local]

mediatypes = MediatypesLookup ()

