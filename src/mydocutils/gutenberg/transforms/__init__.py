#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""

gutenberg.py

Copyright 2012 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Transforms for the Project Gutenberg flavor.

"""

import datetime
import textwrap

from docutils import nodes
import docutils.transforms
import docutils.transforms.parts

from epubmaker.lib.Logger import error, info, debug, warn
from epubmaker.lib.DublinCore import DublinCore
from epubmaker.mydocutils import nodes as mynodes

# pylint: disable=W0142

class SubRefToVarTransform (docutils.transforms.Transform):
    """
    Transforms subref nodes in 'pg' namespace into var nodes.

    We need to save some subrefs for later processing. The standard
    subref processing happens too early (ie. before docinfo is
    collected). So we transform subrefs into variables, await docinfo
    to be processed, and then process the variables.

    """

    default_priority = 219
    """ Before substitition def variables """


    def apply (self):
        for ref in self.document.traverse (nodes.substitution_reference):
            refname = ref['refname']
            if refname.startswith ('pg.'):
                var = mynodes.variable ()
                var['name'] = refname
                ref.replace_self (var)


class VariablesTransform (docutils.transforms.Transform):
    """ Replaces mynodes.var with parameters from metadata. """

    default_priority = 342
    """ After DocInfoCollector. """

    def apply(self):
        doc = self.document
        meta = doc.meta_block
        defs = doc.substitution_defs

        def getone (name, default = None):
            """ Get first value. """
            if name in meta:
                return meta[name][0]
            return default

        def getmany (name, default = []):
            """ Get list of all values. """
            return meta.get (name, default)

        def sub (var, nodes):
            var.replace_self (nodes)

        title = getone ('DC.Title', 'No Title')
        short_title = getone ('PG.Title', title)
        short_title = short_title.split ('\n', 1)[0]

        language = getmany ('DC.Language', ['en'])
        language = map (lambda x: DublinCore.language_map.get (
            x, 'Unknown').title (), language)
        language = DublinCore.strunk (language)

        copyrighted = getone ('PG.Rights', '').lower () == 'copyrighted'

        for variable in doc.traverse (mynodes.variable):
            name = variable['name']

            if name == 'pg.upcase-title':
                sub (variable, [ nodes.inline ('', short_title.upper ()) ])

            elif name == 'pg.produced-by':
                producers = getmany ('PG.Producer')
                if producers:
                     sub (variable, [ nodes.inline ('', u'Produced by %s.' %
                                                    DublinCore.strunk (producers)) ])
                else:
                    sub (variable, [])

            elif name == 'pg.credits':
                sub (variable, [ nodes.inline ('', getone ('PG.Credits', '')) ])

            elif name == 'pg.bibrec-url':
                url = 'http://www.gutenberg.org/ebooks/%s' % getone ('PG.Id', '999999')
                sub (variable, [ nodes.reference ('', '', nodes.inline ('', url), refuri = url) ])

            elif name in ('pg.copyrighted-header', 'pg.copyrighted-footer'):
                if copyrighted:
                    subdef_copy = defs[name].deepcopy ()
                    sub (variable, subdef_copy.children)
                else:
                    sub (variable, [])

            elif name == 'pg.machine-header':
                tw = textwrap.TextWrapper (
                    width = 72,
                    initial_indent = u'Title: ',
                    subsequent_indent = u' ' * 7)

                if '\n' in title:
                    maintitle, subtitle = title.split ('\n', 1)
                    s = tw.fill (maintitle)
                    s += '\n'
                    tw.initial_indent = tw.subsequent_indent
                    s += tw.fill (subtitle)
                else:
                    s = tw.fill (title)
                s += '\n\n'

                tw.initial_indent = u'Author: '
                tw.subsequent_indent = u' ' * 8
                s += tw.fill (DublinCore.strunk (getmany ('DC.Creator', ['Unknown'])))
                s += '\n\n'

                date = getone ('PG.Released', '')
                try:
                    date = datetime.datetime.strptime (date, '%Y-%m-%d')
                    date = datetime.datetime.strftime (date, '%B %d, %Y')
                except ValueError:
                    date = 'unknown date'
                s += u'Release Date: %s [EBook #%s]\n' % (date, getone ('PG.Id', '999999'))

                for item in getmany ('PG.Reposted', []):
                    try:
                        date, comment = item.split (None, 1)
                    except ValueError:
                        date = item
                        comment = None
                    try:
                        date = datetime.datetime.strptime (date, '%Y-%m-%d')
                        date = datetime.datetime.strftime (date, '%B %d, %Y')
                    except ValueError:
                        date = 'unknown date'

                    s += u'Reposted: %s' % date
                    if comment:
                        s += u' [%s]' % comment
                    s += '\n'

                s += u'\nLanguage: %s\n\n' % language
                s += u'Character set encoding: %s' % doc.settings.encoding.upper ()

                sub (variable, [ nodes.inline ('', nodes.Text (s)) ])
