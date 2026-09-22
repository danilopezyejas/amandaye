"""Small bounded JSON transport. Never log URLs containing provider credentials."""
import json
import socket
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code, status=None):
        self.code = code
        self.status = status
        super().__init__(code)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Fixed official endpoints must not forward query-string credentials elsewhere.
        return None


def _invalid_constant(value):
    raise ValueError("non_finite_json")


def public_response(url, timeout, *, form=None):
    """Bounded public dashboard read; never execute scripts or follow redirects.

    Ecowitt uses POST for read-only dashboard queries. HTTP Date anchors its
    relative sensor dates, even if an upstream cache serves an older response.
    """
    headers = {"Accept": "application/json" if form is not None else "text/html",
               "User-Agent": "Amandaye-Conditions/1.0"}
    body = None
    if form is not None:
        body = urlencode(form).encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=headers)
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(MAX_PAGE_BYTES + 1)
            date_header = response.headers.get("Date")
        if len(body) > MAX_PAGE_BYTES:
            raise ProviderError("invalid_response")
        text = body.decode("utf-8")
        reference = None
        if date_header:
            try:
                reference = parsedate_to_datetime(date_header)
                if reference.utcoffset() is None:
                    reference = None
            except (TypeError, ValueError, OverflowError):
                pass
        if form is None:
            return text, reference
        data = json.loads(text, parse_constant=_invalid_constant)
        if not isinstance(data, dict):
            raise ProviderError("invalid_response")
        return data, reference
    except HTTPError as exc:
        raise ProviderError("http_error", exc.code) from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("timeout") from None
    except URLError as exc:
        code = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connection_error"
        raise ProviderError(code) from None
    except (ValueError, UnicodeError):
        raise ProviderError("invalid_response") from None
    except OSError:
        raise ProviderError("connection_error") from None


def get_json(url, params, timeout):
    request = Request(
        url + "?" + urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "Amandaye-Conditions/1.0"},
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProviderError("invalid_response")
        data = json.loads(body, parse_constant=_invalid_constant)
        if not isinstance(data, dict):
            raise ProviderError("invalid_response")
        return data
    except HTTPError as exc:
        raise ProviderError("http_error", exc.code) from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("timeout") from None
    except URLError as exc:
        code = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connection_error"
        raise ProviderError(code) from None
    except (ValueError, UnicodeError):
        raise ProviderError("invalid_response") from None
    except OSError:
        raise ProviderError("connection_error") from None
