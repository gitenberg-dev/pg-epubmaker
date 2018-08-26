#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""

CommonOptions.py

Copyright 2010 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Common options for programs.

"""

from __future__ import with_statement

import optparse
import ConfigParser
import os

class Struct (object):
    pass

def add_common_options (op):
    """ Add options common to all programs. """
    
    op.add_option (
        "-c", "--config",
        metavar  = "FILE",
        dest     = "config_name", 
        action   = "store",
        default  = "config",
        help     = "use config file (default: config)")

    op.add_option (
        "-v", "--verbose",
        dest     = "verbose", 
        action   = "count",
        help     = "be verbose (-v -v be more verbose)")

    op.add_option (
        "--validate",
        dest     = "validate", 
        action   = "count",
        help     = "validate epub through epubcheck")

    op.add_option (
        "--section",
        metavar  = "TAG.CLASS",
        dest     = "section_tags", 
        default  = [],
        action   = "append",
        help     = "split epub on TAG.CLASS")


def get_parser (**kwargs):
    op = optparse.OptionParser (**kwargs)
    add_common_options (op)
    return op
    

def parse_args (op, params = {}, defaults = {}):
    (options, args) = op.parse_args ()

    cp = ConfigParser.SafeConfigParser (params)
    cp.read ( [options.config_name,
               os.path.expanduser ('~/.epubmaker.conf'),
               '/etc/epubmaker.conf' ] )

    options.config = Struct ()

    for name, value in defaults.iteritems ():
        setattr (options.config, name.upper (), value)
        
    for section in cp.sections ():
        for name, value in cp.items (section):
            #if value == 'None':
            #    value = None
            # print section, name, value
            setattr (options.config, name.upper (), value)

    return options, args


