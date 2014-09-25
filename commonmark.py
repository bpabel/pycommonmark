"""
CommonMark compliant Markdown parser in Python.
Copyright (c) 2014 Brendan Abel 
License: BSD3

"""

import re
import logging
from pprint import pprint, pformat

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


ESCAPABLE = '[!"#$%&\'()*+,./:<=>?@[\\\\\\]^_`{|}~-]'
ESCAPED_CHAR = '\\\\' + ESCAPABLE
IN_DOUBLE_QUOTES = '"(' + ESCAPED_CHAR + '|[^"\\x00])*"'
IN_SINGLE_QUOTES = '\'(' + ESCAPED_CHAR + '|[^\'\\x00])*\''
IN_PARENS = '\\((' + ESCAPED_CHAR + '|[^)\\x00])*\\)'
REG_CHAR = '[^\\\\()\\x00-\\x20]'
IN_PARENS_NOSP = '\\((' + REG_CHAR + '|' + ESCAPED_CHAR + ')*\\)'
TAGNAME = '[A-Za-z][A-Za-z0-9]*'

_block_tag_names = [
    'article', 'header', 'aside', 'hgroup', 'iframe', 'blockquote', 'hr',
    'body', 'li', 'map', 'button', 'object', 'canvas', 'ol', 'caption',
    'output', 'col', 'p', 'colgroup', 'pre', 'dd', 'progress', 'div',
    'section', 'dl', 'table', 'td', 'dt', 'tbody', 'embed', 'textarea',
    'fieldset', 'tfoot', 'figcaption', 'th', 'figure', 'thead', 'footer',
    'footer', 'tr', 'form', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'video',
    'script', 'style',
]
BLOCKTAGNAME = '(?:{0})'.format('|'.join(_block_tag_names))
ATTRIBUTENAME = '[a-zA-Z_:][a-zA-Z0-9:._-]*'
UNQUOTEDVALUE = "[^\"'=<>`\\x00-\\x20]+"
SINGLEQUOTEDVALUE = "'[^']*'"
DOUBLEQUOTEDVALUE = '"[^"]*"'
ATTRIBUTEVALUE = "(?:" + UNQUOTEDVALUE + "|" + SINGLEQUOTEDVALUE + "|" + DOUBLEQUOTEDVALUE + ")"
ATTRIBUTEVALUESPEC = "(?:" + "\\s*=" + "\\s*" + ATTRIBUTEVALUE + ")"
ATTRIBUTE = "(?:" + "\\s+" + ATTRIBUTENAME + ATTRIBUTEVALUESPEC + "?)"
OPENTAG = "<" + TAGNAME + ATTRIBUTE + "*" + "\\s*/?>"
CLOSETAG = "</" + TAGNAME + "\\s*[>]"
OPENBLOCKTAG = "<" + BLOCKTAGNAME + ATTRIBUTE + "*" + "\\s*/?>"
CLOSEBLOCKTAG = "</" + BLOCKTAGNAME + "\\s*[>]"
HTMLCOMMENT = "<!--([^-]+|[-][^-]+)*-->"
PROCESSINGINSTRUCTION = "[<][?].*?[?][>]"
DECLARATION = "<![A-Z]+" + "\\s+[^>]*>"
CDATA = "<!\\[CDATA\\[([^\\]]+|\\][^\\]]|\\]\\][^>])*\\]\\]>"
HTMLTAG = "(?:" + OPENTAG + "|" + CLOSETAG + "|" + HTMLCOMMENT + "|" + PROCESSINGINSTRUCTION + "|" + DECLARATION + "|" + CDATA + ")"
HTMLBLOCKOPEN = "<(?:" + BLOCKTAGNAME + "[\\s/>]" + "|" + "/" + BLOCKTAGNAME + "[\\s>]" + "|" + "[?!])"

reHtmlTag = re.compile('^' + HTMLTAG, re.I)

reHtmlBlockOpen = re.compile('^' + HTMLBLOCKOPEN, re.I)

reLinkTitle = re.compile(
    '^(?:"(' + ESCAPED_CHAR + '|[^"\\x00])*"' +
    '|' +
    '\'(' + ESCAPED_CHAR + '|[^\'\\x00])*\'' +
    '|' +
    '\\((' + ESCAPED_CHAR + '|[^)\\x00])*\\))')

reLinkDestinationBraces = re.compile(
    '^(?:[<](?:[^<>\\n\\\\\\x00]' + '|' + ESCAPED_CHAR + '|' + '\\\\)*[>])')

reLinkDestination = re.compile(
    '^(?:' + REG_CHAR + '+|' + ESCAPED_CHAR + '|' + IN_PARENS_NOSP + ')*')

RE_ESCAPABLE = re.compile(ESCAPABLE)

reAllEscapedChar = re.compile('\\\\(' + ESCAPABLE + ')')

reEscapedChar = re.compile('^\\\\(' + ESCAPABLE + ')')

reHrule = re.compile('^(?:(?:\* *){3,}|(?:_ *){3,}|(?:- *){3,}) *$')

# Matches a character with a special meaning in markdown,
# or a string of non-special characters.
reMain = re.compile(r'(?:[\n`\[\]\\!<&*_]|[^\n`\[\]\\!<&*_]+)', re.M)


class ParseError(Exception):
    """
    Generic exception thrown when errors are encountered parsing markdown.
    """
    pass


class Dumper(object):

    def dump(self):
        d = {}
        for k, v in self.__dict__.items():
            if k == 'parent':
                d[k] = v
            elif isinstance(v, list):
                d[k] = [lv.dump() if hasattr(lv, 'dump') else lv for lv in v]
            else:
                d[k] = v.dump() if hasattr(v, 'dump') else v
        return (self.__class__.__name__, d)



class Block(Dumper):

    def __init__(self):
        super(Block, self).__init__()
        self.tag = ''
        self.t = ''
        self.open = True
        self.last_line_blank = False
        self.start_line = None
        self.end_line = None
        self.start_column = None
        self.inline_content = []
        self.string_content = ''
        self.strings = []
        self.children = []
        self.tight = False
        self.info = ''

    @staticmethod
    def makeBlock(tag, start_line, start_column):
        block = Block()
        block.t = tag
        block.open = True
        block.last_line_blank = False
        block.start_line = start_line
        block.start_column = start_column
        block.end_line = start_line
        block.children = []
        block.parent = None
        # string_content is formed by concatenating strings, in finalize.
        block.string_content = ''
        block.strings = []
        block.inline_content = []
        return block


class Inline(Dumper):

    def __init__(self, c=None, t=None, **kwargs):
        super(Inline, self).__init__()
        self.c = c
        self.t = t
        for k, v in kwargs.items():
            setattr(self, k, v)



# UTILITY FUNCTIONS
def unescape(s):
    """ Replace backslash escapes with literal characters.
    """
    return reAllEscapedChar.sub('$1', s)


def is_blank(s):
    """ Returns true if string contains only space characters.
    """
    return bool(re.match(r'^\s*$', s))


def normalize_reference(s):
    """ 
    Normalize reference label: collapse internal whitespace
    to single space, remove leading/trailing whitespace, case fold.
    
    """
    return re.sub(r'\s+', ' ', s.strip()).upper()


def match_at(regex, s, offset):
    """
    Attempt to match a regex in string s at offset offset.
    Return index of match or null.
    
    """
    match = regex.search(s[offset:])
    if match:
        return offset + match.start()
    return None


def detab_line(text):
    """ Convert tabs to spaces on each line using a 4-space tab stop.
    """
    if '\t' not in text:
        return text
    else:
        def repl(m):
            offset = m.start()
            result = '    '[(offset - repl.last_stop) % 4:]
            repl.last_stop = offset + 1
            return result
        repl.last_stop = 0
        return re.sub(r'\t', repl, text)


def parse_raw_label(s):
    """
    Parse raw link label, including surrounding [], and return
    inline contents.  (Note:  this is not a method of InlineParser.)
    
    """
    # Note: Parse without a refmap we don't want links to resolve
    # in nested brackets!
    return InlineParser().parse(s[1:-2], {})


def splice(inlist, index):
    while len(inlist) > index:
        inlist.pop()




# INLINE PARSER

# These are methods of an InlineParser object, defined below.
# An InlineParser keeps track of a subject (a string to be
# parsed) and a position in that subject.

class InlineParser(Dumper):

    def __init__(self):
        super(InlineParser, self).__init__()
        self.subject = ''
        self.label_nest_level = 0
        self.pos = 0
        self.refmap = dict()

    def match(self, regex):
        """
        If regex matches at current position in the subject, advance
        position in subject and return the match otherwise return None.
        
        """
        m = regex.search(self.subject[self.pos:])
        if m:
            self.pos += (m.start() + len(m.group(0)))
            return m.group(0)
        else:
            return None

    def peek(self):
        """
        Returns the character at the current subject position, or None if
        there are no more characters.
        """
        try:
            return self.subject[self.pos]
        except IndexError:
            return None


    def spnl(self):
        """
        Parse zero or more space characters, including at most one newline.
        """
        self.match(re.compile(r'^ *(?:\n *)?'))
        return 1

    def parse_backticks(self, inlines):
        """
        All of the parsers below try to match something at the current position
        in the subject.  If they succeed in matching anything, they
        push an inline element onto the 'inlines' list.  They return the
        number of characters parsed (possibly 0).
        
        Attempt to parse backticks, adding either a backtick code span or a
        literal sequence of backticks to the 'inlines' list.    
        
        """
        startpos = self.pos
        ticks = self.match(re.compile(r'^`+'))
        if not ticks:
            return 0

        after_open_ticks = self.pos
        found_code = False

        match = self.match(re.compile(r'`+', re.M))
        while not found_code and match:
            if match == ticks:
                inline = Inline(
                    t='Code',
                    c=re.sub(r'[ \n]+', ' ', self.subject[after_open_ticks:(self.pos - len(ticks))]).strip(),
                )
                inlines.append(inline)
                return self.pos - startpos

            match = self.match(re.compile(r'`+', re.M))

        inlines.append(Inline(t='Str', c=ticks))
        self.pos = after_open_ticks
        return self.pos - startpos



    def parseEscaped(self, inlines):
        """
        Parse a backslash-escaped special character, adding either the escaped
        character, a hard line break (if the backslash is followed by a newline),
        or a literal backslash to the 'inlines' list.        
        
        """
        subj = self.subject
        pos = self.pos
        if subj[pos] == '\\':
            if subj[pos + 1] == '\n':
                inlines.append(Inline(t='Hardbreak'))
                self.pos = self.pos + 2
                return 2
            elif RE_ESCAPABLE.search(subj[pos + 1]):
                inlines.append(Inline(t='Str', c=subj[pos + 1]))
                self.pos = self.pos + 2
                return 2
            else:
                self.pos += 1
                inlines.append(Inline(t='Str', c='\\'))
                return 1

        else:
            return 0


    def parse_autolink(self, inlines):
        """ Attempt to parse an autolink (URL or email in pointy brackets).        
        """
        dest = None
        m = self.match(re.compile(r'^<([a-zA-Z0-9.!#$%&\'*+\\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>'))
        if m:
            dest = m[1:-1]
            inlines.append(
                Inline(
                    t='Link',
                    label=[Inline(t='Str', c=dest)],
                    destination='mailto:' + dest,
                )
            )
            return len(m)

        else:
            keys = [
                'coap', 'doi', 'javascript', 'aaa', 'aaas', 'about', 'acap',
                'cap', 'cid', 'crid', 'data', 'dav', 'dict', 'dns', 'file',
                'ftp', 'geo', 'go', 'gopher', 'h323', 'http', 'https', 'iax',
                'icap', 'im', 'imap', 'info', 'ipp', 'iris', 'iris.beep',
                'iris.xpc', 'iris.xpcs', 'iris.lwz', 'ldap', 'mailto', 'mid',
                'msrp', 'msrps', 'mtqp', 'mupdate', 'news', 'nfs', 'ni',
                'nih', 'nntp', 'opaquelocktoken', 'pop', 'pres', 'rtsp',
                'service', 'session', 'shttp', 'sieve', 'sip', 'sips', 'sms',
                'snmp', 'soap.beep', 'soap.beeps', 'tag', 'tel', 'telnet',
                'tftp', 'thismessage', 'tn3270', 'tip', 'tv', 'urn', 'vemmi',
                'ws', 'wss', 'xcon', 'xcon-userid', 'xmlrpc.beep',
                'xmlrpc.beeps', 'xmpp', 'z39.50r', 'z39.50s', 'adiumxtra',
                'afp', 'afs', 'aim', 'apt', 'attachment', 'aw', 'beshare',
                'bitcoin', 'bolo', 'callto', 'chrome', 'chrome-extension',
                'com-eventbrite-attendee', 'content', 'cvs', 'dlna-playsingle',
                'dlna-playcontainer', 'dtn', 'dvb', 'ed2k', 'facetime',
                'feed', 'finger', 'fish', 'gg', 'git', 'gizmoproject', 'gtalk',
                'hcp', 'icon', 'ipn', 'irc', 'irc6', 'ircs', 'itms', 'jar',
                'jms', 'keyparc', 'lastfm', 'ldaps', 'magnet', 'maps',
                'market', 'message', 'mms', 'ms-help', 'msnim', 'mumble',
                'mvn', 'notes', 'oid', 'palm', 'paparazzi', 'platform',
                'proxy', 'psyc', 'query', 'res', 'resource', 'rmi', 'rsync',
                'rtmp', 'secondlife', 'sftp', 'sgn', 'skype', 'smb', 'soldat',
                'spotify', 'ssh', 'steam', 'svn', 'teamspeak', 'things',
                'udp', 'unreal', 'ut2004', 'ventrilo', 'view-source',
                'webcal', 'wtai', 'wyciwyg', 'xfire', 'xri', 'ymsgr',
            ]
            m = self.match(re.compile(r'^<(?:{0}):[^<>\x00-\x20]*>'.format('|'.join(keys))))
            if m:
                dest = m[1:-1]
                inlines.append(Inline(t='Link', label=[Inline(t='Str', c=dest)], destination=dest))
                return len(m)

            else:
                return 0

    def parse_html_tag(self, inlines):
        """ Attempt to parse a raw HTML tag.
        """
        m = self.match(reHtmlTag)
        if m:
            inlines.append(Inline(t='Html', c=m))
            return len(m)
        else:
            return 0


    def scan_delims(self, c):
        """
        Scan a sequence of characters == c, and return information about
        the number of delimiters and whether they are positioned such that
        they can open and/or close emphasis or strong emphasis.  A utility
        function for strong/emph parsing.        
        
        """
        numdelims = 0
        startpos = self.pos

        char_before = '\n' if self.pos == 0 else self.subject[self.pos - 1]
        while self.peek() == c:
            numdelims += 1
            self.pos += 1

        char_after = self.peek() or '\n'

        can_open = numdelims > 0 and numdelims <= 3 and not re.search(r'\s', char_after)
        can_close = numdelims > 0 and numdelims <= 3 and not re.search(r'\s', char_before)
        if c == '_':
            can_open = can_open and not re.search(r'[a-z0-9]', char_before, re.I)
            can_close = can_close and not re.search(r'[a-z0-9]', char_after, re.I)

        # Rewind pos.
        self.pos = startpos
        return {'numdelims': numdelims, 'can_open': can_open, 'can_close': can_close}

    def parse_emphasis(self, inlines):
        """
        Attempt to parse emphasis or strong emphasis in an efficient way,
        with no backtracking.
        
        """
        startpos = self.pos
        c = None
        first_close = 0
        nxt = self.peek()

        if nxt == '*' or nxt == '_':
            c = nxt
        else:
            return 0

        # Get opening delimiters.
        res = self.scan_delims(c)
        self.pos += res['numdelims']

        # We provisionally add a literal string.  If we match appropriate
        # closing delimiters, we'll change this to Strong or Emph.
        inlines.append(Inline(t='Str', c=self.subject[self.pos - res['numdelims']:self.pos]))

        # Record the position of this opening delimiter
        delimpos = len(inlines) - 1

        if not res['can_open'] or res['numdelims'] == 0:
            return 0

        first_close_delims = 0

        if res['numdelims'] == 1:
            while True:
                res = self.scan_delims(c)
#                 pprint([i.dump() for i in inlines])
#                 print 'RES', pformat(res)
                if res['numdelims'] >= 1 and res['can_close']:
                    self.pos += 1
                    # Convert the inline at delimpos, currently a string with the delim,
                    # into an Emph whose contents are the succeeding inlines.
                    inlines[delimpos].t = 'Emph'
                    inlines[delimpos].c = inlines[delimpos + 1:]
                    splice(inlines, delimpos + 1)
                    break
                else:
                    if self.parse_inline(inlines) == 0:
                        break
#             print 'END'
#             pprint([i.dump() for i in inlines])
            return self.pos - startpos

        elif res['numdelims'] == 2:  # We started with ** or __
            while True:
                res = self.scan_delims(c)
                if res['numdelims'] >= 2 and res['can_close']:
                    self.pos += 2
                    inlines[delimpos].t = 'Strong'
                    inlines[delimpos].c = inlines[delimpos + 1:]
                    splice(inlines, delimpos + 1)
                    break
                else:
                    if self.parse_inline(inlines) == 0:
                        break

            return self.pos - startpos


        elif res['numdelims'] == 3:
            while True:
                res = self.scan_delims(c)
                if res['numdelims'] >= 1 and res['numdelims'] <= 3 and res['can_close'] and res['numdelims'] != first_close_delims:
                    if first_close_delims == 1 and res['numdelims'] > 2:
                        res['numdelims'] = 2
                    elif first_close_delims == 2:
                        res['numdelims'] = 1
                    elif res['numdelims'] == 3:
                        # If we opened with ***, then we interpret *** as ** followed by *
                        # giving us <strong><em>
                        res['numdelims'] = 1

                    self.pos += res['numdelims']

                    if first_close > 0:  # If we've already passed the first closer.
                        inlines[delimpos].t = 'Strong' if first_close_delims == 1 else 'Emph'
                        inlines[delimpos].c = [Inline(
                            t='Emph' if first_close_delims == 1 else 'Strong',
                            c=inlines[delimpos + 1:first_close],
                        )]
                        inlines[delimpos].c.extend(inlines[first_close + 1:])
                        break

                    else:
                        # This is the first closer for now, add literal string.
                        # We'll change this when we hit the second closer.
                        inlines.append(Inline(t='Str', c=self.subject[self.pos - res['numdelims']:self.pos]))
                        first_close = len(inlines) - 1
                        first_close_delims = res['numdelims']
                else:
                    if self.parse_inline(inlines) == 0:
                        break

            return self.pos - startpos

        else:
            return 1

        return 0

    def parse_link_title(self):
        """
        Attempt to parse link title (sans quotes), returning the string
        or null if no match.
        
        """
        title = self.match(reLinkTitle)
        if title:
            # Chop off quotes from title and unescape
            return unescape(title[1:-2])
        else:
            return None

    def parse_link_description(self):
        """
        Attempt to parse link destination, returning the string or
        null if no match.
        
        """
        res = self.match(reLinkDestinationBraces)
        if res:
            return unescape(res[1:-2])
        else:
            res = self.match(reLinkDestination)
            if res is not None:
                return unescape(res)
            else:
                return None

    def parse_link_label(self):
        """
        Attempt to parse a link label, returning number of characters parsed.
        
        """
        if self.peek() != '[':
            return 0

        startpos = self.pos
        nest_level = 0
        if self.label_nest_level > 0:
            # If we've already checked to the end of this subject
            # for a label, even with a different starting [, we
            # know we won't find one here and we can just return.
            # This avoids lots of backtracking.
            # Note:  nest level 1 would be: [foo [bar]
            #        nest level 2 would be: [foo [bar [baz]
            self.label_nest_level -= 1
            return 0

        self.pos += 1  # Advance past [ char.
        c = self.peek()
        while c and (c != ']' or nest_level > 0):
            if c == '`':
                self.parse_backticks([])
            elif c == '<':
                self.parse_autolink([]) or self.parse_html_tag([]) or self.parse_string([])
            elif c == '[':  # Nested []
                nest_level += 1
                self.pos += 1
            elif c == ']':  # Nested []
                nest_level -= 1
                self.pos += 1
            elif c == '\\':
                self.parseEscaped([])
            else:
                self.parse_string([])
            c = self.peek()

        if c == ']':
            self.label_nest_level = 0
            self.pos += 1  # Advance past ]
            return self.pos - startpos
        else:
            if not c:
                self.label_nest_level = nest_level
            self.pos = startpos
            return 0


    def parse_link(self, inlines):
        """ Attempt to parse a link.  If successful, add the link to inlines.
        """
        startpos = self.pos

        n = self.parse_link_label()
        if n == 0:
            return 0

        rawlabel = self.subject[startpos:n]

        # If we got this far, we've parse a label.
        # Try to parse an explicit link: [label](url "title")
        if self.peek() == '(':
            self.pos += 1
            if self.spnl():
                dest = self.parseLinkDestination()
                if dest is not None and self.spnl():
                    # Make sure there's a space before the title
                    match = re.search(r'^\s', self.subject[self.pos - 1])
                    if match:
                        title = self.parse_link_title() or ''
                        if self.spnl() and self.match(re.compile(r'^\)')):
                            inlines.append(
                                Inline(
                                    t='Link',
                                    destination=dest,
                                    title=title,
                                    label=parse_raw_label(rawlabel),
                                )
                            )
                            return self.pos - startpos

            self.pos = startpos
            return 0

        # If we're here, it wasn't an explicit link. Try to parse a reference link.
        # first, see if there's another label
        savepos = self.pos
        self.spnl()
        beforelabel = self.pos
        n = self.parse_link_label()
        if n == 2:
            # Empty second label.
            reflabel = rawlabel
        elif n > 0:
            reflabel = self.subject[beforelabel, beforelabel + n]
        else:
            self.pos = savepos
            reflabel = rawlabel

        # Lookup rawlabel in refmap
        link = self.refmap[normalize_reference(reflabel)]
        if link:
            inlines.append(
                Inline(
                    t='Link',
                    destination=link.destination,
                    title=link.title,
                    label=parse_raw_label(rawlabel),
                )
            )
            return self.pos - startpos

        else:
            self.pos = startpos
            return 0

        # Nothing worked, rewind
        self.pos = startpos
        return 0

    def parse_entity(self, inlines):
        """ Attempt to parse an entity, adding to inlines if successful.
        """
        m = self.match(re.compile(r'^&(?:#x[a-f0-9]{1,8}|#[0-9]{1,8}|[a-z][a-z0-9]{1,31})', re.I))
        if m:
            inlines.append(Inline(t='Entity', c=m))
            return len(m)
        else:
            return 0

    def parse_string(self, inlines):
        """
        Parse a run of ordinary characters, or a single character with
        a special meaning in markdown, as a plain string, adding to inlines.
        
        """
        m = self.match(reMain)
        if m:
            inlines.append(Inline(t='Str', c=m))
            return len(m)
        else:
            return 0

    def parse_newline(self, inlines):
        """
        Parse a newline.  If it was preceded by two spaces, return a hard
        line break otherwise a soft line break.
        
        """
        if self.peek() == '\n':
            self.pos += 1
            last = inlines[-1] if inlines else None
            if last and last.t == 'Str' and last.c[-2:] == '  ':
                last.c = re.sub(r' *$', '', last.c)
                inlines.append(Inline(t='Hardbreak'))
            else:
                if last and last.t == 'Str' and last.c[-1] == ' ':
                    last.c = last.c[:-1]
                inlines.append(Inline(t='Softbreak'))

            return 1
        else:
            return 0


    def parse_image(self, inlines):
        """
        Attempt to parse an image.  If the opening '!' is not followed
        by a link, add a literal '!' to inlines.
        
        """
        if self.match(re.compile(r'^!')):
            n = self.parse_link(inlines)
            if n == 0:
                inlines.append(Inline(t='Str', c='!'))
                return 1
            elif inlines and inlines[-1] and inlines[-1].t == 'Link':
                inlines[-1].t = 'Image'
                return n + 1
            else:
                raise ParseError("Shouldn't happen: parsing Image.")

        else:
            return 0

    def parse_reference(self, s, refmap):
        """ Attempt to parse a link reference, modifying refmap.
        """
        self.subject = s
        self.pos = 0
        startpos = self.pos

        # Label
        match_chars = self.parse_link_label()
        if match_chars == 0:
            return 0
        else:
            rawlabel = self.subject[:match_chars]

        # Colon
        if self.peek() == ':':
            self.pos += 1
        else:
            self.pos = startpos
            return 0

        # Link URL
        self.spnl()

        dest = self.parse_link_description()
        if not dest:
            self.pos = startpos
            return 0

        beforetitle = self.pos
        self.spnl()
        title = self.parse_link_title()
        if title is None:
            title = ''
            # Rewind before spaces
            self.pos = beforetitle

        normlabel = normalize_reference(rawlabel)

        if normlabel not in refmap:
            refmap[normlabel] = Inline(destination=dest, title=title)

        return self.pos - startpos

    def parse_inline(self, inlines):
        """
        Parse the next inline element in subject, advancing subject position
        and adding the result to 'inlines'.        
        
        """
        c = self.peek()
        r = None
        if c == '\n':
            r = self.parse_newline(inlines)
        elif c == '\\':
            r = self.parseEscaped(inlines)
        elif c == '`':
            r = self.parse_backticks(inlines)
        elif c == '*' or c == '_':
            r = self.parse_emphasis(inlines)
        elif c == '[':
            r = self.parse_link(inlines)
        elif c == '!':
            r = self.parse_image(inlines)
        elif c == '<':
            r = self.parse_autolink(inlines) or self.parse_html_tag(inlines)
        elif c == '&':
            r = self.parse_entity(inlines)

        return r or self.parse_string(inlines)

    def parse(self, s, refmap):
        """ Parse s as a list of inlines, using refmap to resolve references.
        """
        self.subject = s
        self.pos = 0
        self.refmap = refmap or {}
        inlines = []
        while self.parse_inline(inlines):
            pass
        return inlines



class ListData(Dumper):

    def __init__(self):
        super(ListData, self).__init__()
        self.type = None
        self.bullet_char = None
        self.start = None
        self.delimiter = None
        self.padding = None


def parseListMarker(line, offset):
    """
    Parse a list marker and return data on the marker (type,
    start, delimiter, bullet character, padding) or null.
    
    """
    rest = line[offset:]
    spaces_after_marker = None
    data = ListData()
    if reHrule.search(rest):
        return None

    match = re.match(r'^[*+-]( +|$)', rest)
    if match:
        spaces_after_marker = len(match.group(1))
        data.type = 'Bullet'
        data.bullet_char = match.group(0)[0]

    else:
        match = re.match(r'^(\d+)([.)])( +|$)', rest)
        if match:
            spaces_after_marker = len(match.group(3))
            data.type = 'Ordered'
            data.start = int(match.group(1))
            data.delimiter = match.group(2)

        else:
            return None

    blank_item = len(match.group(0)) == len(rest)
    if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
        data.padding = len(match.group(0)) - spaces_after_marker + 1
    else:
        data.padding = len(match.group(0))

    return data


def listsMatch(list_data, item_data):
    """
    Returns true if the two list items are of the same type,
    with the same delimiter and bullet character.  This is used
    in agglomerating list items into lists.

    """
    return (list_data.type == item_data.type and
            list_data.delimiter == item_data.delimiter and
            list_data.bullet_char == item_data.bullet_char)


def endsWithBlankLine(block):
    """
    Returns true if block ends with a blank line, descending if needed
    into lists and sublists.    
    
    """
    if block.last_line_blank:
        return True
    if block.t in ['List', 'ListItem'] and block.children:
        return endsWithBlankLine(block.children[-1])
    else:
        return False


def canContain(parent_type, child_type):
    """ Returns true if parent block can contain child block.
    """
    return (parent_type in ['Document', 'BlockQuote', 'ListItem'] or
            (parent_type == 'List' and child_type == 'ListItem'))


def acceptsLines(block_type):
    """ Returns true if block type can accept lines of text.
    """
    return block_type in ['Paragraph', 'IndentedCode', 'FencedCode']


class DocParser(Dumper):

    def __init__(self):
        super(DocParser, self).__init__()
        self.doc = Block.makeBlock('Document', 1, 1)
        self.tip = self.doc
        self.refmap = dict()
        self.inlineParser = InlineParser()
        self.top = 0

    def break_out_of_lists(self, block, line_number):
        """
        Break out of all containing lists, resetting the tip of the
        document to the parent of the highest list, and finalizing
        all the lists.  (This is used to implement the "two blank lines
        break of of all lists" feature.)        
        
        """
        b = block
        last_list = None
        while True:
            if b.t == 'List':
                last_list = b
            b = b.parent
            if not b:
                break

        if last_list:
            while block != last_list:
                self.finalize(block, line_number)
                block = block.parent

            self.finalize(last_list, line_number)
            self.tip = last_list.parent




    def add_line(self, line, offset):
        """
        Add a line to the block at the tip.  We assume the tip
        can accept lines -- that check should be done before calling this.
        
        """
        s = line[offset:]
        if not self.tip.open:
            raise ParseError('Attempted to add line ({0}) to closed container.'.format(line))
        self.tip.strings.append(s)

    def add_child(self, tag, line_number, offset):
        """
        Add block of type tag as a child of the tip.  If the tip can't
        accept children, close and finalize it and try its parent,
        and so on til we find a block that can accept children.   
        
        """
        while not canContain(self.tip.t, tag):
            self.finalize(self.tip, line_number)

        column_number = offset + 1  # Offset 0 = column 1
        new_block = Block.makeBlock(tag, line_number, column_number)
        self.tip.children.append(new_block)
        new_block.parent = self.tip
        self.tip = new_block
        return new_block

    def incorporate_line(self, line, line_number):
        """
        Analyze a line of text and update the document appropriately.
        We parse markdown text by calling this on each line of input,
        then finalizing the document.        
        
        """
        all_matched = True
        offset = 0
        CODE_INDENT = 4
        container = self.doc
        oldtip = self.tip
        blank = False

        # Convert tabs to spaces.
        line = detab_line(line)

        # For each containing block, try to parse the associated line start.
        # Bail out on failure: container will point to the last matching block.
        # Set all_matched to false if not all containers match.
        while container.children:
            last_child = container.children[-1]
            if not last_child.open:
                break
            container = last_child

            match = match_at(re.compile(r'[^ ]'), line, offset)
            if match is None:
                first_nonspace = len(line)
                blank = True
            else:
                first_nonspace = match
                blank = False
            indent = first_nonspace - offset

            if container.t == 'BlockQuote':
                matched = (indent <= 3 and line[first_nonspace] == '>')
                if matched:
                    offset = first_nonspace + 1
                    if line[offset] == ' ':
                        offset += 1
                else:
                    all_matched = False

            elif container.t == 'ListItem':
                if indent >= container.list_data.marker_offset + container.list_data.padding:
                    offset += container.list_data.marker_offset + container.list_data.padding
                elif blank:
                    offset = first_nonspace
                else:
                    all_matched = False

            elif container.t == 'IndentedCode':
                if indent >= CODE_INDENT:
                    offset += CODE_INDENT
                elif blank:
                    offset = first_nonspace
                else:
                    all_matched = False

            elif container.t in ['ATXHeader', 'SetextHeader', 'HorizontalRule']:
                # A header can never containe >1 line, so fail to match:
                all_matched = False

            elif container.t == 'FencedCode':
                # Skip optional spaces of fence offset.
                i = container.fence_offset
                while i > 0 and line[offset] == ' ':
                    offset += 1
                    i -= 1

            elif container.t == 'HtmlBlock':
                if blank:
                    all_matched = False

            elif container.t == 'Paragraph':
                if blank:
                    container.last_line_blank = True
                    all_matched = False
            else:
                pass

            if not all_matched:
                container = container.parent  # Back up to last matching block.
                break

        last_matched_container = container

        # This function is used to finalize and close any unmatched
        # blocks.  We aren't ready to do this now, because we might
        # have a lazy paragraph continuation, in which case we don't
        # want to close unmatched blocks.  So we store this closure for
        # use later, when we have more information.
        def closeUnmatchedBlocks(mythis):
            closeUnmatchedBlocks.oldtip = oldtip
            # finalize any blocks not matched
            while not closeUnmatchedBlocks.already_done and closeUnmatchedBlocks.oldtip != last_matched_container:
                mythis.finalize(closeUnmatchedBlocks.oldtip, line_number)
                closeUnmatchedBlocks.oldtip = closeUnmatchedBlocks.oldtip.parent
            closeUnmatchedBlocks.already_done = True

        closeUnmatchedBlocks.already_done = False

        # Check to see if we've hit 2nd blank line, if so break out of list.
        if blank and container.last_line_blank:
            self.break_out_of_lists(container, line_number)

        # Unless last matched container is a code block, try new container starts,
        # adding children to the last matched container.
        while (container.t not in ['FencedCode', 'IndentedCode', 'HtmlBlock'] and
               match_at(re.compile(r'^[ #`~*+_=<>0-9-]'), line, offset) is not None):

            match = match_at(re.compile(r'[^ ]'), line, offset)
            if match is None:
                first_nonspace = len(line)
                blank = True
            else:
                first_nonspace = match
                blank = False

            indent = first_nonspace - offset

            if indent >= CODE_INDENT:
                # Indented code
                if self.tip.t != 'Paragraph' and not blank:
                    offset += CODE_INDENT
                    closeUnmatchedBlocks(self)
                    oldtip = closeUnmatchedBlocks.oldtip
                    container = self.add_child('IndentedCode', line_number, offset)
                else:  # Indent > 4 in a lazy paragraph continuation.
                    break

            elif line[first_nonspace] == '>':
                # Blockquote
                offset = first_nonspace + 1
                # Optional following space
                if line[offset] == ' ':
                    offset += 1
                closeUnmatchedBlocks(self)
                oldtip = closeUnmatchedBlocks.oldtip
                container = self.add_child('BlockQuote', line_number, offset)

            else:
                match = re.match(r'^#{1,6}(?: +|$)', line[first_nonspace:])
                if match:
                    # ATX Header
                    offset = first_nonspace + len(match.group(0))
                    closeUnmatchedBlocks(self)
                    oldtip = closeUnmatchedBlocks.oldtip
                    container = self.add_child('ATXHeader', line_number, first_nonspace)
                    container.level = len(match.group(0).strip())  # Numver of #'s
                    # Remove trailing #'s
                    container.strings = [re.sub(r'(?:(\\#) *#*| *#+) *$', '\g<1>', line[offset:])]
                    break

                else:
                    match = re.match(r'^`{3,}(?!.*`)|^~{3,}(?!.*~)', line[first_nonspace:])
                    if match:
                        # Fenced code block
                        fence_length = len(match.group(0))
                        closeUnmatchedBlocks(self)
                        oldtip = closeUnmatchedBlocks.oldtip
                        container = self.add_child('FencedCode', line_number, first_nonspace)
                        container.fence_length = fence_length
                        container.fence_char = match.group(0)[0]
                        container.fence_offset = first_nonspace - offset
                        offset = first_nonspace + fence_length
                        break

                    elif match_at(reHtmlBlockOpen, line, first_nonspace) is not None:
                        # Html block
                        closeUnmatchedBlocks(self)
                        oldtip = closeUnmatchedBlocks.oldtip
                        container = self.add_child('HtmlBlock', line_number, first_nonspace)
                        # Note, we don't adjsut offset because the tag is part of the text
                        break

                    else:
                        match = re.match(r'^(?:=+|-+) *$', line[first_nonspace:])
                        if container.t == 'Paragraph' and len(container.strings) == 1 and match:
                            # Setext header line
                            closeUnmatchedBlocks(self)
                            oldtip = closeUnmatchedBlocks.oldtip
                            container.t = 'SetextHeader'  # Convert Paragraph to SetextHeader
                            container.level = 1 if match.group(0)[0] == '=' else 2
                            offset = len(line)

                        elif match_at(reHrule, line, first_nonspace) is not None:
                            # Hrule
                            closeUnmatchedBlocks(self)
                            oldtip = closeUnmatchedBlocks.oldtip
                            container = self.add_child('HorizontalRule', line_number, first_nonspace)
                            offset = len(line) - 1
                            break

                        else:
                            data = parseListMarker(line, first_nonspace)
                            if data:
                                # List item
                                closeUnmatchedBlocks(self)
                                oldtip = closeUnmatchedBlocks.oldtip
                                data.marker_offset = indent
                                offset = first_nonspace + data.padding

                                # Add the list if needed
                                if container.t != 'List' or not listsMatch(container.list_data, data):
                                    container = self.add_child('List', line_number, first_nonspace)
                                    container.list_data = data

                                # Add the list item
                                container = self.add_child('ListItem', line_number, first_nonspace)
                                container.list_data = data

                            else:
                                break

            if acceptsLines(container.t):
                # If it's a line container, it can't contain other containers.
                break

        # What remains at the offset is a text line.  Add the text to the
        # appropriate container.
        match = match_at(re.compile(r'[^ ]'), line, offset)
        if match is None:
            first_nonspace = len(line)
            blank = True
        else:
            first_nonspace = match
            blank = False
        indent = first_nonspace - offset

        # First check for a lazy paragraph continuation
        if self.tip != last_matched_container and not blank and self.tip.t == 'Paragraph' and self.tip.strings:
            # Laxy paragraph continuation
            self.last_line_blank = False
            self.add_line(line, offset)

        else:
            # Not a lay continuation
            # Finalize any blocks not matched
            closeUnmatchedBlocks(self)
            oldtip = closeUnmatchedBlocks.oldtip

            # Block quote lines are never blank as they start with >
            # and we don't count blanks in fenced code for purposes of tight/loose
            # lists or breaking out of lists.  We also don't set last_line_blank
            # on an empty list item.
            container.last_line_blank = (
                blank and
                    not (container.t in ['BlockQuote', 'FencedCode'] or
                        (container.t == 'ListItem' and
                            not container.children and
                            container.start_line == line_number)))

            cont = container
            while cont.parent:
                cont.parent.last_line_blank = False
                cont = cont.parent

            if container.t in ['IndentedCode', 'HtmlBlock']:
                self.add_line(line, offset)

            elif container.t == 'FencedCode':
                # Check for closing code fence.
                match = re.match(r'^(?:`{3,}|~{3,})(?= *$)', line[first_nonspace:])
                if indent <= 3 and line[first_nonspace] == container.fence_char and match and len(match.group(0)) > container.fence_length:
                    # Don't add closing fence to container instead, close it.
                    self.finalize(container, line_number)
                else:
                    self.add_line(line, offset)

            elif container.t in ['ATXHeader', 'SetextHeader', 'HorizontalRule']:
                # Nothing to do we already added the contents
                pass
            else:
                if acceptsLines(container.t):
                    self.add_line(line, first_nonspace)
                elif blank:
                    pass
                elif container.t not in ['HorizontalRule', 'SetextHeader']:
                    # Create Paragraph container for line.
                    container = self.add_child('Paragraph', line_number, first_nonspace)
                    self.add_line(line, first_nonspace)
                else:
                    logger.warning('Line {0} with container type {1} did not match any condition.'.format(line_number, container.t))


    def finalize(self, block, line_number):
        """
        Finalize a block.  Close it and do any necessary postprocessing,
        e.g. creating string_content from strings, setting the 'tight'
        or 'loose' status of a list, and parsing the beginnings
        of paragraphs for reference definitions.  Reset the tip to the
        parent of the closed block.
        
        """
        pos = None
        # Don't do anything if the block is already closed.
        if not block.open:
            return 0
        block.open = False
        if line_number > block.start_line:
            block.end_line = line_number - 1
        else:
            block.end_line = line_number

        if block.t == 'Paragraph':
            block.string_content = re.sub(r'^  *', '', '\n'.join(block.strings), re.M)
            # Try parsing the beginning as link reference definitions.
            pos = self.inlineParser.parse_reference(block.string_content, self.refmap)
            while block.string_content[0] == '[' and pos:
                block.string_content = block.string_content[pos:]
                if is_blank(block.string_content):
                    block.t = 'ReferenceDef'
                    break
                pos = self.inlineParser.parse_reference(block.string_content, self.refmap)

        elif block.t in ['ATXHeader', 'SetextHeader', 'HtmlBlock']:
            block.string_content = '\n'.join(block.strings)

        elif block.t == 'IndentedCode':
            block.string_content = re.sub(r'(\n *)*$', '\n', '\n'.join(block.strings))

        elif block.t == 'FencedCode':
            # First line becomes info string.
            block.info = unescape(block.strings[0].strip())
            if len(block.strings) == 1:
                block.string_content = ''
            else:
                block.string_content = '\n'.join(block.strings[1:]) + '\n'

        elif block.t == 'List':
            block.tight = True  # Tight by default

            for i, item in enumerate(block.children):
                # Check for non-finallist item ending with blank line.
                last_item = (i == len(block.children) - 1)
                if endsWithBlankLine(item) and not last_item:
                    block.tight = False
                    break

                # Recurse into children of list item, to see if there are
                # spaces between any of them.
                for j, subitem in enumerate(item.children):
                    last_subitem = (j == len(item.children) - 1)
                    if endsWithBlankLine(subitem) and not (last_item and last_subitem):
                        block.tight = False
                        break

        else:
            pass

        self.tip = block.parent or self.top

    def process_inlines(self, block):
        """
        Walk through a block & children recursively, parsing string content
        into inline content where appropriate.
        
        """
        if block.t in ['Paragraph', 'SetextHeader', 'ATXHeader']:
            block.inline_content = self.inlineParser.parse(block.string_content.strip(), self.refmap)
            block.string_content = ''
        else:
            pass

        if block.children:
            for child in block.children:
                self.process_inlines(child)

    def parse(self, text):
        """ The main parsing function.  Returns a parsed document AST.
        """
        self.doc = Block.makeBlock('Document', 1, 1)
        self.tip = self.doc
        self.refmap = dict()
        lines = re.split(r'\r\n|\n|\r', re.sub(r'\n$', '', text))
        for i, line in enumerate(lines):
            self.incorporate_line(line, i + 1)
        while self.tip:
            self.finalize(self.tip, len(lines) - 1)
#         print 'PREINLINE'
#         pprint(self.doc.dump())
        self.process_inlines(self.doc)
        return self.doc


class HtmlRenderer(Dumper):

    def __init__(self):
        super(HtmlRenderer, self).__init__()
        self.blocksep = '\n'
        self.innersep = '\n'
        self.softbreak = '\n'

    @staticmethod
    def in_tags(tag, attrs, contents, selfclosing=False):
        result = '<' + tag
        if attrs:
            for attr in attrs:
                if attr is None:
                    break
                result += u' {0}="{1}"'.format(attr[0], attr[1])

        if contents:
            result += u'>{0}</{1}>'.format(contents, tag)
        elif selfclosing:
            result += u' />'
        else:
            result += u'></{0}>'.format(tag)
        return result

    def escape(self, s, preserve_entities=False):
        if preserve_entities:
            s = re.sub(r'[&](?![#](x[a-f0-9]{1,8}|[0-9]{1,8})|[a-z][a-z0-9]{1,31})', '&amp', s, flags=re.I)
            s = re.sub(r'[<]', '&lt', s)
            s = re.sub(r'[>]', '&gt', s)
            s = re.sub(r'["]', '&quote', s)
            return s
        else:
            s = re.sub(r'[&]', '&amp', s)
            s = re.sub(r'[<]', '&lt', s)
            s = re.sub(r'[>]', '&gt', s)
            s = re.sub(r'["]', '&quote', s)
            return s

    def render_inline(self, inline):
        """ Render an inline element as HTML.
        """
        attrs = None
        if inline.t == 'Str':
            return self.escape(inline.c)
        elif inline.t == 'Softbreak':
            return self.softbreak
        elif inline.t == 'Hardbreak':
            return self.in_tags('br', [], "", True) + '\n'
        elif inline.t == 'Emph':
            return self.in_tags('em', [], self.render_inlines(inline.c))
        elif inline.t == 'Strong':
            return self.in_tags('strong', [], self.render_inlines(inline.c))
        elif inline.t == 'Html':
            return inline.c
        elif inline.t == 'Entity':
            return inline.c
        elif inline.t == 'Link':
            attrs = [['href', self.escape(inline.destination, True)]]
            if inline.title:
                attrs.append(['title', self.escape(inline.title, True)])
            return self.in_tags('a', attrs, self.render_inlines(inline.label))
        elif inline.t == 'Image':
            attrs = [
                ['src', self.escape(inline.destination, True)],
                ['alt', self.escape(self.render_inlines(inline.label))],
            ]
            if inline.title:
                attrs.append(['title', self.escape(inline.title, True)])
            return self.in_tags('img', attrs, "", True)
        elif inline.t == 'Code':
            return self.in_tags('code', [], self.escape(inline.c))
        else:
            logger.warning('Unknown inline type: {}'.format(inline.t))
            return ''

    def render_inlines(self, inlines):
        """ Render a list of inlines.
        """
        result = []
        for inline in inlines:
            result.append(self.render_inline(inline))
        return ''.join(result)

    def render_block(self, block, in_tight_list=False):
        """ Render a single block element.
        """
        tag = None
        attr = None
        info_words = None

        if block.t == 'Document':
            whole_doc = self.render_blocks(block.children)
            return '' if whole_doc == '' else whole_doc + '\n'

        elif block.t == 'Paragraph':
            if in_tight_list:
                return self.render_inlines(block.inline_content)
            else:
                return self.in_tags('p', [], self.render_inlines(block.inline_content))

        elif block.t == 'BlockQuote':
            filling = self.render_blocks(block.children)
            filling = self.innersep if filling == '' else self.innersep + filling + self.innersep
            return self.in_tags('blockquote', [], filling)

        elif block.t == 'ListItem':
            return self.in_tags('li', [], self.render_blocks(block.children, in_tight_list).strip())

        elif block.t == 'List':
            tag = 'ul' if block.list_data.type == 'Bullet' else 'ol'
            if not block.list_data.start or block.list_data.start == 1:
                attr = []
            else:
                attr = [['start', block.list_data.start.toString()]]

            return self.in_tags(tag, attr, self.innersep +
                          self.render_blocks(block.children, block.tight) +
                          self.innersep)

        elif block.t in ['ATXHeader', 'SetextHeader']:
            tag = 'h{}'.format(block.level)
            return self.in_tags(tag, [], self.render_inlines(block.inline_content))

        elif block.t == 'IndentedCode':
            return self.in_tags('pre', [], self.in_tags('code', [], self.escape(block.string_content)))

        elif block.t == 'FencedCode':
            info_words = re.split(r' +', block.info)
            if not info_words or not len(info_words)[0]:
                attr = []
            else:
                attr = [['class', 'language-' + self.escape(info_words[0], True)]]
            return self.in_tags('pre', [], self.in_tags('code', attr, self.escape(block.string_content)))

        elif block.t == 'HtmlBlock':
            return block.string_content

        elif block.t == 'ReferenceDef':
            return ""

        elif block.t == 'HorizontalRule':
            return self.in_tags('hr', [], "", True)

        else:
            logger.warning('Unknown block type: {}'.format(block.t))
            return ''

    def render_blocks(self, blocks, in_tight_list=False):
        """ Render a list of block elements, separated by this.blocksep.
        """
        result = []
        for block in blocks:
            result.append(self.render_block(block, in_tight_list))
        return self.blocksep.join(result)



