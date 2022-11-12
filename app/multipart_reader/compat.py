try:
    from urllib.parse import parse_qsl, unquote  # noqa
except ImportError:
    from urllib import unquote as _unquote
    from urlparse import parse_qsl  # noqa

    def unquote(value, encoding, errors):
        return _unquote(value).decode(encoding, errors)
