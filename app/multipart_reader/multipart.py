import binascii
import base64
import json
import re
import warnings
import zlib

from collections import deque

from . import hdrs

from .helpers import parse_mimetype
from .multidict import CIMultiDict
from .protocol import HttpParser
from .compat import parse_qsl, unquote


__all__ = ('MultipartReader',
           'BadContentDispositionHeader', 'BadContentDispositionParam',
           'parse_content_disposition', 'content_disposition_filename')

CHAR = set(chr(i) for i in range(0, 128))
CTL = set(chr(i) for i in range(0, 32)) | {chr(127), }
SEPARATORS = {'(', ')', '<', '>', '@', ',', ';', ':', '\\', '"', '/', '[', ']',
              '?', '=', '{', '}', ' ', chr(9)}
TOKEN = CHAR ^ CTL ^ SEPARATORS


class BadEqMixin(object):
    def __eq__(self, other):
        if isinstance(other, RuntimeWarning):
            message = other.message
        return self.message == message


class BadContentDispositionHeader(BadEqMixin, RuntimeWarning):
    pass


class BadContentDispositionParam(BadEqMixin, RuntimeWarning):
    pass


def parse_content_disposition(header):
    def is_token(string):
        return string and TOKEN >= set(string)

    def is_quoted(string):
        return string[0] == string[-1] == '"'

    def is_rfc5987(string):
        return is_token(string) and string.count("'") == 2

    def is_extended_param(string):
        return string.endswith('*')

    def is_continuous_param(string):
        pos = string.find('*') + 1
        if not pos:
            return False
        substring = string[pos:-1] if string.endswith('*') else string[pos:]
        return substring.isdigit()

    def unescape(text, chars=''.join(map(re.escape, CHAR))):
        return re.sub('\\\\([{}])'.format(chars), '\\1', text)

    if not header:
        return None, {}

    disptype_parts = header.split(';')
    disptype, parts = disptype_parts[0], disptype_parts[1:]

    if not is_token(disptype):
        warnings.warn(BadContentDispositionHeader(header))
        return None, {}

    params = {}
    for item in parts:
        if '=' not in item:
            warnings.warn(BadContentDispositionHeader(header))
            return None, {}

        key, value = item.split('=', 1)
        key = key.lower().strip()
        value = value.lstrip()

        if key in params:
            warnings.warn(BadContentDispositionHeader(header))
            return None, {}

        if not is_token(key):
            warnings.warn(BadContentDispositionParam(item))
            continue

        elif is_continuous_param(key):
            if is_quoted(value):
                value = unescape(value[1:-1])
            elif not is_token(value):
                warnings.warn(BadContentDispositionParam(item))
                continue

        elif is_extended_param(key):
            if is_rfc5987(value):
                encoding, _, value = value.split("'", 2)
                encoding = encoding or 'utf-8'
            else:
                warnings.warn(BadContentDispositionParam(item))
                continue

            try:
                value = unquote(value, encoding, 'strict')
            except UnicodeDecodeError:
                warnings.warn(BadContentDispositionParam(item))
                continue

        else:
            if is_quoted(value):
                value = unescape(value[1:-1].lstrip('\\/'))
            elif not is_token(value):
                warnings.warn(BadContentDispositionHeader(header))
                return None, {}

        params[key] = value

    return disptype.lower(), params


def content_disposition_filename(params):
    if not params:
        return None
    elif 'filename*' in params:
        return params['filename*']
    elif 'filename' in params:
        return params['filename']
    else:
        parts = []
        fnparams = sorted((key, value)
                          for key, value in params.items()
                          if key.startswith('filename*'))
        for num, (key, value) in enumerate(fnparams):
            _, tail = key.split('*', 1)
            if tail.endswith('*'):
                tail = tail[:-1]
            if tail == str(num):
                parts.append(value)
            else:
                break
        if not parts:
            return None
        value = ''.join(parts)
        if "'" in value:
            encoding, _, value = value.split("'", 2)
            encoding = encoding or 'utf-8'

            return unquote(value, encoding, 'strict')

        return value


class BodyPartReader(object):
    """Multipart reader for single body part."""

    chunk_size = 8192

    def __init__(self, boundary, headers, content):
        self.headers = headers
        self._boundary = boundary
        self._content = content
        self._at_eof = False
        length = self.headers.get(hdrs.CONTENT_LENGTH, None)
        self._length = int(length) if length is not None else None
        self._read_bytes = 0
        self._unread = deque()


    def __iter__(self):
        return self

    def __next__(self):
        # for Python 3
        return self.next()

    def next(self):
        data = self.read()

        if data is None:
            raise StopIteration()

        return data

    def read(self, decode=False):
        """Reads body part data.

        :param bool decode: Decodes data following by encoding
                            method from `Content-Encoding` header. If it missed
                            data remains untouched

        :rtype: bytearray
        """
        if self._at_eof:
            return
        data = bytearray()
        if self._length is None:
            while not self._at_eof:
                data.extend(self.readline())
        else:
            while not self._at_eof:
                data.extend(self.read_chunk(self.chunk_size))
        if decode:
            return self.decode(data)
        
        self._firstLine = False
        return data

    def read_chunk(self, size=chunk_size):
        """Reads body part content chunk of the specified size.
        The body part must has `Content-Length` header with proper value.

        :param int size: chunk size

        :rtype: bytearray
        """
        if self._at_eof:
            return
        assert self._length is not None, \
            'Content-Length required for chunked read'
        chunk_size = min(size, self._length - self._read_bytes)
        chunk = self._content.read(chunk_size)
        self._read_bytes += len(chunk)
        if self._read_bytes == self._length:
            self._at_eof = True
            assert b'\r\n' == self._content.readline(), \
                'reader did not read all the data or it is malformed'
        return chunk

    def readline(self):
        """Reads body part by line by line.

        :rtype: bytearray
        """
        if self._at_eof:
            return

        if self._unread:
            line = self._unread.popleft()
        else:
            line = self._content.readline()

        if line.startswith(self._boundary):
            # the very last boundary may not come with \r\n,
            # so set single rules for everyone
            sline = line.rstrip(b'\r\n')
            boundary = self._boundary
            last_boundary = self._boundary + b'--'
            # ensure that we read exactly the boundary, not something alike
            if sline == boundary or sline == last_boundary:
                self._at_eof = True
                self._unread.append(line)
                return ''
        else:
            next_line = self._content.readline()
            if next_line.startswith(self._boundary):
                line = line.rstrip(b'\r\n')  # strip CRLF but only once
            self._unread.append(next_line)

        return line

    def release(self):
        """Lke :meth:`read`, but reads all the data to the void.

        :rtype: None
        """
        if self._at_eof:
            return
        if self._length is None:
            while not self._at_eof:
                self.readline()
        else:
            while not self._at_eof:
                self.read_chunk(self.chunk_size)

    def text(self, encoding=None):
        """Lke :meth:`read`, but assumes that body part contains text data.

        :param str encoding: Custom text encoding. Overrides specified
                             in charset param of `Content-Type` header

        :rtype: str
        """
        data = self.read(decode=True) or b''
        encoding = encoding or self.get_charset(default='utf-8')
        return data.decode(encoding)

    def json(self, encoding=None):
        """Lke :meth:`read`, but assumes that body parts contains JSON data.

        :param str encoding: Custom JSON encoding. Overrides specified
                             in charset param of `Content-Type` header
        """
        data = self.read(decode=True)
        if not data:
            return
        encoding = encoding or self.get_charset(default='utf-8')
        return json.loads(data.decode(encoding))

    def form(self, encoding=None):
        """Lke :meth:`read`, but assumes that body parts contains form
        urlencoded data.

        :param str encoding: Custom form encoding. Overrides specified
                             in charset param of `Content-Type` header
        """
        data = self.read(decode=True)
        if not data:
            return None
        encoding = encoding or self.get_charset(default='utf-8')
        return parse_qsl(data.rstrip().decode(encoding))

    def at_eof(self):
        """Returns ``True`` if the boundary was reached or
        ``False`` otherwise.

        :rtype: bool
        """
        return self._at_eof

    def decode(self, data):
        """Decodes data according the specified `Content-Encoding`
        or `Content-Transfer-Encoding` headers value.

        Supports ``gzip``, ``deflate`` and ``identity`` encodings for
        `Content-Encoding` header.

        Supports ``base64``, ``quoted-printable`` encodings for
        `Content-Transfer-Encoding` header.

        :param bytearray data: Data to decode.

        :raises: :exc:`RuntimeError` - if encoding is unknown.

        :rtype: bytes
        """
        if hdrs.CONTENT_TRANSFER_ENCODING in self.headers:
            data = self._decode_content_transfer(data)
        if hdrs.CONTENT_ENCODING in self.headers:
            return self._decode_content(data)
        return data

    def _decode_content(self, data):
        encoding = self.headers[hdrs.CONTENT_ENCODING].lower()

        if encoding == 'deflate':
            return zlib.decompress(bytes(data), -zlib.MAX_WBITS)
        elif encoding == 'gzip':
            return zlib.decompress(bytes(data), 16 + zlib.MAX_WBITS)
        elif encoding == 'identity':
            return data
        else:
            raise RuntimeError('unknown content encoding: {}'.format(encoding))

    def _decode_content_transfer(self, data):
        encoding = self.headers[hdrs.CONTENT_TRANSFER_ENCODING].lower()

        if encoding == 'base64':
            return base64.b64decode(data)
        elif encoding == 'quoted-printable':
            return binascii.a2b_qp(data)
        else:
            raise RuntimeError('unknown content transfer encoding: {}'
                               ''.format(encoding))

    def get_charset(self, default=None):
        """Returns charset parameter from ``Content-Type`` header or default.
        """
        ctype = self.headers.get(hdrs.CONTENT_TYPE, '')
        _, _, _, params = parse_mimetype(ctype)
        return params.get('charset', default)

    @property
    def filename(self):
        """Returns filename specified in Content-Disposition header or ``None``
        if missed or header is malformed."""
        _, params = parse_content_disposition(
            self.headers.get(hdrs.CONTENT_DISPOSITION))
        return content_disposition_filename(params)


class MultipartReader(object):
    """Multipart body reader."""

    #: Multipart reader class, used to handle multipart/* body parts.
    #: None points to type(self)
    multipart_reader_cls = None
    #: Body part reader class for non multipart/* content types.
    part_reader_cls = BodyPartReader

    def __init__(self, headers, content):
        self.headers = CIMultiDict(headers)
        self._boundary = ('--' + self._get_boundary()).encode()
        self._content = content
        self._last_part = None
        self._at_eof = False
        self._unread = []
        self._firstLine = True

    def at_eof(self):
        """Returns ``True`` if the final boundary was reached or
        ``False`` otherwise.

        :rtype: bool
        """
        return self._at_eof

    def __iter__(self):
        return self

    def __next__(self):
        # for Python 3
        return self.next()

    def next(self):
        """Emits the next multipart body part."""
        if self._at_eof:
            raise StopIteration()
        self._maybe_release_last_part()
        self._read_boundary()
        if self._at_eof:  # we just read the last boundary, nothing to do there
            raise StopIteration()
        self._last_part = self.fetch_next_part()
        return self._last_part

    def release(self):
        """Reads all the body parts to the void till the final boundary."""
        for item in self:
            item.release()

    def fetch_next_part(self):
        """Returns the next body part reader."""
        headers = self._read_headers()
        return self._get_part_reader(headers)

    def _get_part_reader(self, headers):
        """Dispatches the response by the `Content-Type` header, returning
        suitable reader instance.

        :param dict headers: Response headers
        """
        ctype = headers.get(hdrs.CONTENT_TYPE, '')
        mtype, _, _, _ = parse_mimetype(ctype)
        if mtype == 'multipart':
            if self.multipart_reader_cls is None:
                return type(self)(headers, self._content)
            return self.multipart_reader_cls(headers, self._content)
        else:
            return self.part_reader_cls(self._boundary, headers, self._content)

    def _get_boundary(self):

        mtype, _, _, params = parse_mimetype(self.headers[hdrs.CONTENT_TYPE])
        assert mtype == 'multipart', 'multipart/* content type expected'

        if 'boundary' not in params:
            raise ValueError('boundary missed for Content-Type: %s'
                             % self.headers[hdrs.CONTENT_TYPE])

        boundary = params['boundary']
        if len(boundary) > 70:
            raise ValueError('boundary %r is too long (70 chars max)'
                             % boundary)

        return boundary

    def _readline(self):
        if self._firstLine == True:
            line = self._content.readline()
            if line == b'\r\n':
                line = self._content.readline() 
            self._firstLine = False   
        if self._unread:
            return self._unread.pop()
        #return self._content.readline()
        return line

    def _read_boundary(self):
        chunk = self._readline().rstrip()
        if chunk == self._boundary:
            pass
        elif chunk == self._boundary + b'--':
            self._at_eof = True
        else:
            raise ValueError('Invalid boundary %r, expected %r'
                             % (chunk, self._boundary))

    def _read_headers(self):
        lines = ['']
        while True:
            chunk = self._content.readline()
            chunk = chunk.decode().strip()
            lines.append(chunk)
            if not chunk:
                break
        parser = HttpParser()
        headers, _, _ = parser.parse_headers(lines)
        return headers

    def _maybe_release_last_part(self):
        """Ensures that the last read body part is read completely."""
        if self._last_part is not None:
            if not self._last_part.at_eof():
                self._last_part.release()
            self._unread.extend(self._last_part._unread)
            self._last_part = None
