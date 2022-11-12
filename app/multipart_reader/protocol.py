"""Http related parsers and protocol."""
import re

from . import hdrs
from . import errors

from .multidict import CIMultiDict


__all__ = ('HttpParser',)

CONTINUATION = (' ', '\t')
HDRRE = re.compile('[\x00-\x1F\x7F()<>@,;:\[\]={} \t\\\\\"]')


class HttpParser(object):

    def __init__(self, max_line_size=8190, max_headers=32768,
                 max_field_size=8190):
        self.max_line_size = max_line_size
        self.max_headers = max_headers
        self.max_field_size = max_field_size

    def parse_headers(self, lines):
        """Parses RFC2822 headers from a stream.
        Line continuations are supported. Returns list of header name
        and value pairs. Header name is in upper case.
        """
        close_conn = None
        encoding = None
        headers = CIMultiDict()

        lines_idx = 1
        line = lines[1]

        while line:
            header_length = len(line)

            if ':' not in line:
                raise errors.InvalidHeader(line)

            # Parse initial header name : value pair.
            name, value = line.split(':', 1)

            name = name.strip(' \t').upper()
            if HDRRE.search(name):
                raise errors.InvalidHeader(name)

            # next line
            lines_idx += 1
            line = lines[lines_idx]

            # consume continuation lines
            continuation = line and line[0] in CONTINUATION

            if continuation:
                value = [value]
                while continuation:
                    header_length += len(line)
                    if header_length > self.max_field_size:
                        raise errors.LineTooLong(
                            'limit request headers fields size')
                    value.append(line)

                    # next line
                    lines_idx += 1
                    line = lines[lines_idx]
                    continuation = line[0] in CONTINUATION
                value = '\r\n'.join(value)
            else:
                if header_length > self.max_field_size:
                    raise errors.LineTooLong(
                        'limit request headers fields size')

            value = value.strip()

            # keep-alive and encoding
            if name == hdrs.CONNECTION:
                v = value.lower()
                if v == 'close':
                    close_conn = True
                elif v == 'keep-alive':
                    close_conn = False
            elif name == hdrs.CONTENT_ENCODING:
                enc = value.lower()
                if enc in ('gzip', 'deflate'):
                    encoding = enc

            headers.add(name, value)

        return headers, close_conn, encoding
