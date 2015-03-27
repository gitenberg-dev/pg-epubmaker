#!/usr/bin/env python
#  -*- mode: python; indent-tabs-mode: nil; -*- coding: utf-8 -*-

"""

DublinCore.py

Copyright 2009 by Marcello Perathoner

Distributable under the GNU General Public License Version 3 or newer.

DublinCore metadata swiss army knife.

"""

import re
import datetime
import textwrap

import lxml
from lxml.builder import ElementMaker

import epubmaker.lib.GutenbergGlobals as gg
from epubmaker.lib.GutenbergGlobals import NS, Struct, xpath
from epubmaker.lib.Logger import debug, error, exception


ROLES = """ adp | Adapter
 ann | Annotator
 arr | Arranger
 art | Artist
 aut | Author
 aft | Author of afterword, colophon, etc.
 aui | Author of introduction, etc.
 clb | Collaborator
 cmm | Commentator
 com | Compiler
 cmp | Composer
 cnd | Conductor
 ctb | Contributor
 cre | Creator
 dub | Dubious author
 edt | Editor
 egr | Engraver
 frg | Forger
 ill | Illustrator
 lbt | Librettist
 mrk | Markup editor
 mus | Musician
 oth | Other
 pat | Patron
 prf | Performer
 pht | Photographer
 prt | Printer
 pro | Producer
 prg | Programmer
 pfr | Proofreader
 pbl | Publisher
 res | Researcher
 rev | Reviewer
 sng | Singer
 spk | Speaker
 trc | Transcriber
 trl | Translator
 unk | Unknown role """

LANGS = """ af  | Afrikaans
 ale | Aleut
 arp | Arapaho
 br  | Breton
 bg  | Bulgarian
 rmr | Caló
 ca  | Catalan
 ceb | Cebuano
 zh  | Chinese
 cs  | Czech
 da  | Danish
 nl  | Dutch
 en  | English
 eo  | Esperanto
 fi  | Finnish
 fr  | French
 fy  | Frisian
 fur | Friulian
 gla | Gaelic, Scottish
 gl  | Galician
 kld | Gamilaraay
 de  | German
 bgi | Giangan
 el  | Greek
 he  | Hebrew
 hu  | Hungarian
 is  | Icelandic
 ilo | Iloko
 ia  | Interlingua
 iu  | Inuktitut
 ga  | Irish
 iro | Iroquoian
 it  | Italian
 ja  | Japanese
 csb | Kashubian
 kha | Khasi
 ko  | Korean
 la  | Latin
 lt  | Lithuanian
 mi  | Maori
 myn | Mayan Languages
 enm | Middle English
 nah | Nahuatl
 nap | Napoletano-Calabrese
 nai | North American Indian
 no  | Norwegian
 oc  | Occitan
 ang | Old English
 pl  | Polish
 pt  | Portuguese
 ro  | Romanian
 ru  | Russian
 sa  | Sanskrit
 sr  | Serbian
 es  | Spanish
 sv  | Swedish
 tl  | Tagalog
 tr  | Turkish
 cy  | Welsh
 yi  | Yiddish """


class _HTML_Writer (object):
    """ Write metadata suitable for inclusion in HTML.

    Build a <meta> or <link> element and 
    add it to self.metadata. 

    """

    def __init__ (self):
        self.metadata = []

    @staticmethod
    def _what (what):
        """ Transform dcterms:title to DCTERMS.title. """
        what = str (what).split (':')
        what[0] = what[0].upper ()
        return '.'.join (what)

    def literal (self, what, literal, scheme = None):
        """ Write <meta name=what content=literal scheme=scheme> """
        if literal is None:
            return
        params = {'name' : self._what (what), 'content': literal}
        if scheme:
            params['scheme'] = self._what (scheme)
        self.metadata.append (ElementMaker ().meta (**params))

    def uri (self, what, uri):
        """ Write <link rel=what href=uri> """
        if uri is None:
            return
        self.metadata.append (ElementMaker ().link (
                rel = self._what (what), href = str (uri)))
   

# file extension we hope to be able to parse
PARSEABLE_EXTENSIONS = str.split ('txt html htm tex tei xml')

RE_MARC_SUBFIELD = re.compile (r"\$[a-z]\b")

class DublinCore (object):
    """ Hold DublinCore attributes.

    Read and output them in various formats.

    """

    SI_prefixes = (
        (1024 ** 3, u'%.2f GB'),
        (1024 ** 2, u'%.1f MB'),
        (1024,      u'%.0f kB'),
        )

    # load local role map as default
    role_map = {}
    inverse_role_map = {}
    for line in ROLES.splitlines ():
        pk, role = line.split ('|')
        pk = pk.strip ()
        role = role.strip ().lower ()
        role_map[pk] = role
        inverse_role_map[role] = pk

    # load local language map as default
    language_map = {}
    inverse_language_map = {}
    for line in LANGS.splitlines ():
        pk, lang = line.split ('|')
        pk = pk.strip ()
        lang = lang.strip ().lower ()
        language_map[pk] = lang
        inverse_language_map[lang] = pk


    def __init__ (self):
        self.title = 'No title'
        self.title_file_as = self.title
        self.source = None
        self.languages = []
        self.created = None
        self.publisher = None
        self.rights = None
        self.authors = []
        self.subjects = []
        self.bookshelves = []
        self.loccs = []
        self.categories = []
        self.dcmitypes = [] # similar to categories but based on the DCMIType vocabulary
        self.release_date = None
        self.edition = None
        self.contents = None
        self.encoding = None
        self.notes = None
        self.downloads = 0
        self.score = 1

        
    @staticmethod
    def format_author_date (author):
        """ Format: Twain, Mark, 1835-1910 """

        def format_dates (d1, d2):
            """ Format dates """
            # Hack to display 9999? if only d2 is set
            if d2 and not d1:
                if (d2 < 0):
                    return "%d? BCE" % abs (d2)
                return "%d?" % d2
            if not d1:
                return ''
            if (d2 and d1 != d2):
                d3 = max (d1, d2)
                if (d3 < 0):
                    return "%d? BCE" % abs (d3)
                return "%d?" % d3
            if (d1 < 0):
                return "%d BCE" % abs (d1)
            return str (d1)

        born = format_dates (author.birthdate, author.birthdate2)
        died = format_dates (author.deathdate, author.deathdate2)
        name = gg.normalize (author.name)

        if (born or died):
            return "%s, %s-%s" % (name, born, died)

        return name


    @staticmethod
    def format_author_date_role (author):
        """ Format: Twain, Mark, 1835-1910 [Editor] """
        name = DublinCore.format_author_date (author)
        if (author.marcrel != "cre" and author.marcrel != 'aut'):
            return "%s [%s]" % (name, _(author.role))
        return name


    @staticmethod
    def strip_marc_subfields (s):
        """ Strip MARC subfield markers. """
        return RE_MARC_SUBFIELD.sub ('', s)
        


    @staticmethod
    def make_pretty_name (name):
        """ Reverse author name components """
        rev = ' '.join (reversed (name.split (', ')))
        rev = re.sub (r'\(.*\)', '', rev)
        rev = re.sub (r'\s+', ' ', rev)
        return rev.strip ()


    @staticmethod
    def strunk (list_):
        """ Join a list of terms with appropriate use of ',' and 'and'.

        Tom, Dick, and Harry
        
        """
        if len (list_) > 2:
            list_ = (', '.join (list_[:-1]) + ',', list_[-1])
        return _(u' and ').join (list_)


    def human_readable_size (self, size):
        """ Return human readable string of filesize. """
        if size < 0:
            return u''
        for (threshold, format_string) in self.SI_prefixes:
            if size >= threshold:
                return format_string % (float (size) / threshold)
        return u'%d B' % size


    def make_pretty_title (self, size = 80, cut_nonfiling = False):
        """ Generate a pretty title for ebook. """
        
        def cutoff (title, size):
            """ Cut string off after size characters. """
            return textwrap.wrap (title, size)[0]
        
        title = self.title_file_as if cut_nonfiling else self.title
        
        title = title.splitlines ()[0]
        title = re.sub (r'\s*\$[a-z].*', '', title) # cut before first MARC subfield
        
        title_len = len (title)
        if title_len > size or not self.authors:
            return cutoff (title, size)

        creators = [author for author in self.authors if author.marcrel in ('aut', 'cre')]
        if not creators:
            creators = [author for author in self.authors]
        if not creators:
            return cutoff (title, size)
                    
        fullnames = [self.make_pretty_name (author.name) for author in creators]
        surnames  = [author.name.split (', ')[0] for author in creators]
        
        for tail in (self.strunk (fullnames), self.strunk (surnames)):
            if len (tail) + title_len < size:
                return _(u'{title} by {authors}').format (title = title, authors = tail)

        for tail in (fullnames[0], surnames[0]):
            if len (tail) + title_len < size:
                return _(u'{title} by {authors} et al.').format (title = title, authors = tail)
        
        return cutoff (title, size)
        

    def feed_to_writer (self, writer):
        """ Pipe metadata into writer. """
        lit = writer.literal
        # uri = writer.uri

        lit ('dcterms:title',      self.title)
        lit ('dcterms:source',     self.source)

        for language in self.languages:
            lit ('dcterms:language', language.id, 'dcterms:RFC4646')

        lit ('dcterms:modified', 
             datetime.datetime.now (gg.UTC ()).isoformat (), 
             'dcterms:W3CDTF')


    def to_html (self):
        """ Return a <html:head> element with DC metadata. """

        w = _HTML_Writer ()
        self.feed_to_writer (w)

        e = ElementMaker ()

        head = e.head (
            e.link (rel = "schema.DCTERMS", href = str (NS.dcterms)),
            e.link (rel = "schema.MARCREL", href = str (NS.marcrel)),
            profile = "http://dublincore.org/documents/2008/08/04/dc-html/",
            *w.metadata
            )
        
        return head


    def add_lang_id (self, lang_id):
        """ Add language from language id. """
        language = Struct ()
        language.id = lang_id
        language.language = self.language_map [lang_id].title ()
        self.languages.append (language)
        

    def add_author (self, name, marcrel = 'cre'):
        """ Add author. """

        try:
            role = self.role_map[marcrel]
        except KeyError:
            return False

        # debug ("%s: %s" % (role, names))

        # lowercase De Le La
        for i in str.split ('De Le La'):
            name = re.sub (r'\b%s\b' % i, i.lower (), name)

        name = name.replace ('\\', '')   # remove \ (escape char in RST)
        name = re.sub (r'\s*,\s*,',  ',', name)
        name = re.sub (r',+',        ',', name)
        name = name.replace (',M.D.', '')

        name = re.sub (r'\s*\[.*?\]\s*', ' ', name) # [pseud.]
        name = name.strip ()

        author = Struct ()
        author.name = name
        author.marcrel = marcrel
        author.role = role
        author.name_and_dates = name
        self.authors.append (author)


    def load_from_parser (self, parser):
        """ Load Dublincore from html header. """

        # print (lxml.etree.tostring (parser.xhtml))
        try:
            for meta in xpath (parser.xhtml, "//xhtml:meta[@name='DC.Creator']"):
                author = Struct ()
                author.name = gg.normalize (meta.get ('content'))
                author.marcrel = 'cre'
                author.role = 'creator'
                author.name_and_dates = author.name
                self.authors.append (author)

            for meta in xpath (parser.xhtml, "//xhtml:meta[@name='DC.Contributor']"):
                author = Struct ()
                author.name = gg.normalize (meta.get ('content'))
                author.marcrel = 'ctb'
                author.role = 'contributor'
                author.name_and_dates = author.name
                self.authors.append (author)
                
            for title in xpath (parser.xhtml, "//xhtml:title"):
                self.title = self.title_file_as = gg.normalize (title.text)

            # DC.Title overrides <title>
            for meta in xpath (parser.xhtml, "//xhtml:meta[@name='DC.Title']"):
                self.title = self.title_file_as = gg.normalize (meta.get ('content'))
                
            for elem in xpath (parser.xhtml, "/xhtml:html[@xml:lang]"):
                self.add_lang_id (elem.get (NS.xml.lang))

            for meta in xpath (parser.xhtml, "//xhtml:meta[@name='DC.Created']"):
                self.created = gg.normalize (meta.get ('content'))
                
        except StandardError, what:
            exception (what)


class GutenbergDublinCore (DublinCore):
    """ Parse from PG files. """

    def __init__ (self):
        DublinCore.__init__ (self)
        self.project_gutenberg_id = None
        self.project_gutenberg_title = None
        self.is_format_of = None


    def feed_to_writer (self, writer):
        """ Pipe metadata into writer. """

        DublinCore.feed_to_writer (self, writer)
        
        lit = writer.literal
        uri = writer.uri

        lit ('dcterms:publisher',  self.publisher)
        lit ('dcterms:rights',     self.rights)
        uri ('dcterms:isFormatOf', self.is_format_of)

        for author in self.authors:
            if author.marcrel == 'aut' or author.marcrel == 'cre':
                lit ('dcterms:creator', author.name_and_dates)
            else:
                lit ('marcrel:' + author.marcrel, author.name_and_dates)
                
        for subject in self.subjects:
            lit ('dcterms:subject', subject.subject, 'dcterms:LCSH')

        if self.release_date:
            lit ('dcterms:created', self.release_date.isoformat (), 
                 'dcterms:W3CDTF')
        else:
            if self.created:
                lit ('dcterms:created', self.created, 'dcterms:W3CDTF')


    def load_from_parser (self, parser):
        """ Load DublinCore from Project Gutenberg ebook.

        Worst method. Use as last resort only.

        """

        for body in xpath (parser.xhtml, "//xhtml:body"):
            self.load_from_pgheader (lxml.etree.tostring (body,
                                                          encoding=unicode,
                                                          method='text'))
                                     

    def load_from_rstheader (self, data):
        """ Load DublinCore from RST Metadata.

        """

        self.publisher = 'Project Gutenberg'
        self.rights = 'Public Domain in the USA.'

        re_field = re.compile (r'^\s*:(.+?):\s+', re.UNICODE)
        re_end   = re.compile (r'^[^\s]', re.UNICODE)

        m = schema = name = None
        contents = ''

        for line in data.splitlines ()[:100]:
            m = re_field.match (line)
            m2 = re_end.match (line)

            if name and (m is not None or m2 is not None):
                contents = contents.strip ()
                # debug ("Outputting: %s.%s => %s" % (schema, name, contents))

                if schema == 'pg':
                    if name == 'id':
                        try:
                            self.project_gutenberg_id = int (contents)
                            self.is_format_of = str (NS.ebook) + str (self.project_gutenberg_id)
                        except ValueError:
                            error ('Invalid ebook no. in RST meta: %s' % contents)
                            return False
                    elif name == 'title':
                        self.project_gutenberg_title = contents
                    elif name == 'released':
                        try:
                            self.release_date = datetime.datetime.strptime (
                                contents, '%Y-%m-%d').date ()
                        except ValueError:
                            error ('Invalid date in RST meta: %s' % contents)
                    elif name == 'rights':
                        if contents.lower () == 'copyrighted':
                            self.rights = 'Copyrighted.'

                elif schema == 'dc':
                    if name == 'creator':
                        self.add_author (contents, 'cre')
                    elif name == 'title':
                        self.title = self.title_file_as = contents
                    elif name == 'language':
                        try:
                            self.add_lang_id (contents)
                        except KeyError:
                            error ('Invalid language id RST meta: %s' % contents)
                    elif name == 'created':
                        pass # published date

                elif schema == 'marcrel':
                    self.add_author (contents, name)

                contents = ''
                name = schema = None

            if name:
                contents += '\n' + line.strip ()

            if m is not None:
                try:
                    schema, name = m.group (1).lower ().split ('.', 1)
                    contents = line[m.end ():].strip ()
                except ValueError:
                    schema = name = None
                    contents = ''

        return self.project_gutenberg_id is not None
        

    def load_from_pgheader (self, data):
        """ Load DublinCore from Project Gutenberg ebook.

        Worst method. Use as last resort only.

        """

        def handle_authors (self, role, names):
            """ Handle Author:, Illustrator: etc. line

            Examples of lines we handle are:

            Author: Lewis Carroll, Mark Twain and Chuck Norris
            Illustrator: Jack Tenniel

            """

            try:
                marcrel = self.inverse_role_map[role]
            except KeyError:
                return False

            # replace 'and' with ',' and remove 
            # superfluous white space around ','
            names = re.sub (r'\s*\n\s*',  ',', names)
            names = re.sub (r'[,\s]+and\b',   ',', names)
            names = re.sub (r'\bet\b',    ',', names)
            names = re.sub (r'\bund\b',   ',', names)

            for name in names.split (','):
                self.add_author (name, marcrel)


        def handle_release_date (self, dummy_prefix, date):
            """ Scan Release date: line. """

            m = re.match (r'^(.*?)\s*\[', date)
            if m:
                date = m.group (1)
                date = date.strip ()
                date = re.sub (r'[,\s]+', ' ', date)
                for f in ('%B %d %Y', '%B %Y', '%b %d %Y', '%b %Y', '%Y-%m-%d'):
                    try:
                        self.release_date = datetime.datetime.strptime (date, f).date ()
                        break
                    except ValueError:
                        pass
                    
                if not self.release_date:
                    error ("Cannot understand date: %s" % date)


        def handle_ebook_no (self, text):
            """ Scan ebook no. """

            m = re.search (r'#(\d+)\]', text)
            if m:
                self.project_gutenberg_id = int (m.group (1))
                self.is_format_of = str (NS.ebook) + str (self.project_gutenberg_id)


        def handle_languages (self, dummy_prefix, text):
            """ Scan Language: line """
            for lang in text.lower ().split (','):
                try:
                    language = Struct ()
                    language.id = self.inverse_language_map[lang]
                    language.language = lang.title ()
                    self.languages.append (language)
                except KeyError:
                    pass


        def handle_subject (self, dummy_prefix, suffix):
            """ Handle subject. """
            subject = Struct ()
            subject.id = None
            subject.subject = suffix
            self.subjects.append (subject)
            

        def handle_locc (self, dummy_prefix, suffix):
            """ Handle locc. """
            locc = Struct ()
            locc.id = None
            locc.locc = suffix
            self.loccs.append (locc)
            

        def store (self, prefix, suffix):
            """ Store into attribute. """
            # debug ("store: %s %s" % (prefix, suffix))
            setattr (self, prefix, suffix)
            

        dispatcher = {
            'title':        store,
            'author':       handle_authors,
            'release date': handle_release_date,
            'languages':    handle_languages,
            'subjects':     handle_subject,
            'loccs':        handle_locc,
            'edition':      store,
            'contents':     store,
            'notes':        store,
            'encoding':     store,
            'rights':       store,
            }

        aliases = {
            'authors':                'author',
            'language':               'languages',
            'subject':                'subjects',
            'loc class':              'loccs',
            'loc classes':            'loccs',
            'content':                'contents',
            'note' :                  'notes',
            'character set encoding': 'encoding',
            'copyright':              'rights',
            }


        for role in self.inverse_role_map.keys ():
            dispatcher[role] = handle_authors

        self.publisher = 'Project Gutenberg'
        self.rights = 'Public Domain in the USA.'

        # scan this file

        last_prefix = None
        buf = ''

        for line in data.splitlines ()[:300]:
            line = line.strip (' %') # TeX comments
            # debug ("Line: %s" % line)

            if self.project_gutenberg_id is None:
                handle_ebook_no (self, line.strip ())
            
            if last_prefix and len (line) == 0:
                # debug ("Dispatching: %s => %s" % (last_prefix, buf.strip ()))
                dispatcher[last_prefix] (self, last_prefix, buf.strip ())
                last_prefix = None
                buf = ''
                continue

            if re.search ('START OF', line):
                break

            prefix, sep, suffix = line.partition (':')
            if sep:
                prefix = prefix.lower ()
                prefix = aliases.get (prefix, prefix) # map alias
                if dispatcher.has_key (prefix):
                    if last_prefix:
                        # debug ("Dispatching: %s => %s" % (last_prefix, buf.strip ()))
                        dispatcher[last_prefix] (self, last_prefix, buf.strip ())
                    last_prefix = prefix
                    buf = suffix
                    continue

            buf += '\n' + line

            line = line.lower ()
            if ('audiobooksforfree' in line or
                'literalsystems' in line or
                'librivox' in line or
                'human reading of an ebook' in line):
                if 'Sound' not in self.categories:
                    self.categories.append ('Sound')
                

            if 'copyrighted project gutenberg' in line:
                self.rights = 'Copyrighted.'

        if self.project_gutenberg_id is None:
            raise ValueError ('This is not a Project Gutenberg ebook file.')
