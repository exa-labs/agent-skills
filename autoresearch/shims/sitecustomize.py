"""urllib interception for Inner-LLM sessions (record/replay of Exa traffic).

Injected via PYTHONPATH so the skill's orchestrator (stdlib urllib, hardcoded
https://api.exa.ai) is intercepted without a single edit to the skill itself.
Python imports sitecustomize automatically at startup.

EXA_HTTP_MODE=record — pass through, append the full exchange to EXA_HTTP_LOG.
EXA_HTTP_MODE=replay — raise a clear error for api.exa.ai (replay is offline).
Anything else       — do nothing.
"""
import io
import json
import os

_MODE = os.environ.get("EXA_HTTP_MODE", "")
_LOG = os.environ.get("EXA_HTTP_LOG", "")

if _MODE in ("record", "replay"):
    import urllib.request

    _real_urlopen = urllib.request.urlopen

    def _url_of(req):
        return req if isinstance(req, str) else req.full_url

    def _log(entry):
        if not _LOG:
            return
        try:
            with open(_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    class _Recorded(io.BytesIO):
        """Minimal stand-in for the http response the orchestrator uses
        (.status and .read())."""
        def __init__(self, body, status):
            super().__init__(body)
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    def _urlopen(req, *args, **kwargs):
        url = _url_of(req)
        if "api.exa.ai" not in url:
            return _real_urlopen(req, *args, **kwargs)
        if _MODE == "replay":
            _log({"via": "urllib", "kind": "blocked", "url": url})
            # HTTPError, not RuntimeError: the skill's orchestrator catches
            # HTTPError and skips the run cleanly instead of crashing
            import urllib.error
            raise urllib.error.HTTPError(
                url, 503,
                "LIVE_EXA_DISABLED: this session is a replay; use the frozen run "
                "outputs in ./exa_runs/ instead of calling the Exa API",
                None, io.BytesIO(b'{"error":"LIVE_EXA_DISABLED"}'))
        method = getattr(req, "method", None) or ("GET" if isinstance(req, str) else "GET")
        req_body = getattr(req, "data", None)
        resp = _real_urlopen(req, *args, **kwargs)
        body = resp.read()
        _log({"via": "urllib", "kind": "exchange", "method": method, "url": url,
              "request_body": (req_body or b"").decode("utf-8", "replace"),
              "status": resp.status,
              "response_body": body.decode("utf-8", "replace")})
        return _Recorded(body, resp.status)

    urllib.request.urlopen = _urlopen
