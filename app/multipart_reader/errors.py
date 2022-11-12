

class HttpProcessingError(Exception):
    """Http error.
    Shortcut for raising http errors with custom code, message and headers.
    :param int code: HTTP Error code.
    :param str message: (optional) Error message.
    :param list of [tuple] headers: (optional) Headers to be sent in response.
    """

    code = 0
    message = ''
    headers = None

    def __init__(self, code=None, message='', headers=None):
        if code is not None:
            self.code = code
        self.headers = headers
        self.message = message

        super(HttpProcessingError, self).__init__(
            "{0}, message='{1}'".format(self.code, message))


class BadHttpMessage(HttpProcessingError):

    code = 400
    message = 'Bad Request'

    def __init__(self, message, headers=None):
        super(BadHttpMessage, self).__init__(message=message, headers=headers)


class InvalidHeader(BadHttpMessage):

    def __init__(self, hdr):
        super(InvalidHeader, self).__init__(
            'Invalid HTTP Header: {0}'.format(hdr))
        self.hdr = hdr


class LineTooLong(BadHttpMessage):

    def __init__(self, line, limit='Unknown'):
        super(LineTooLong, self).__init__(
            'got more than {0} bytes when reading {1}'.format(limit, line))
