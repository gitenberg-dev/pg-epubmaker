#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: iso-8859-1 -*-

"""
Logger.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

Logging support.


"""

import logging
from logging import debug, info, warn, error, critical, exception

LOGFORMAT = '%(asctime)s %(levelname)-8s  #%(ebook)-5d %(message)s'

ebook = 0 # global

class CustomFormatter (logging.Formatter):
    """ A custom formatter that adds ebook no. """
    
    def format (self, record):
        """ Add ebook no. to string format params. """
        record.ebook = ebook
        return logging.Formatter.format (self, record)
        
    
def setup (logformat, logfile = None):
    """ Setup logger. """

    # StreamHandler defaults to sys.stderr
    file_handler = logging.FileHandler (logfile) if logfile else logging.StreamHandler ()
    file_handler.setFormatter (CustomFormatter (logformat))
    logging.getLogger ().addHandler (file_handler)
    logging.getLogger ().setLevel (logging.INFO)
    

def set_log_level (level):
    """ Set log level. """
    if level >= 1:
        logging.getLogger ().setLevel (logging.INFO)
    if level >= 2:
        logging.getLogger ().setLevel (logging.DEBUG)


__all__ = 'debug info warn error critical exception'.split ()
