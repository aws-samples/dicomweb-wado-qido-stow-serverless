"""Various helper functions"""


def parse_mimetype(mimetype):
    """Parses a MIME type into its components.
    :param str mimetype: MIME type
    :returns: 4 element tuple for MIME type, subtype, suffix and parameters
    :rtype: tuple
    Example:
    >>> parse_mimetype('text/html; charset=utf-8')
    ('text', 'html', '', {'charset': 'utf-8'})
    """
    if not mimetype:
        return '', '', '', {}

    parts = mimetype.split(';')
    params = []
    for item in parts[1:]:
        if not item:
            continue
        key, value = item.split('=', 1) if '=' in item else (item, '')
        params.append((key.lower().strip(), value.strip(' "')))
    params = dict(params)

    fulltype = parts[0].strip().lower()
    if fulltype == '*':
        fulltype = '*/*'

    mtype, stype = fulltype.split('/', 1) \
        if '/' in fulltype else (fulltype, '')
    stype, suffix = stype.split('+', 1) if '+' in stype else (stype, '')

    return mtype, stype, suffix, params
