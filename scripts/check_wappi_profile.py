"""Read Wappi profile status without sending messages or printing credentials."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the Authorization header to another URL.


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / '.env.wappi.local'
    try:
        values = dict(line.split('=', 1) for line in path.read_text(encoding='utf-8-sig').splitlines()
                      if line.strip() and not line.lstrip().startswith('#') and '=' in line)
        token = values['WAPPI_API_TOKEN'].strip()
        profile = values['WAPPI_LOGIN_PROFILE_ID'].strip()
        if not token or not profile:
            raise ValueError()
    except (OSError, KeyError, ValueError):
        print('WAPPI_CONFIG_MISSING_OR_INVALID')
        return 1
    url = 'https://wappi.pro/api/sync/get/status?' + urllib.parse.urlencode({'profile_id': profile})
    request = urllib.request.Request(url, headers={'Authorization': token, 'Accept': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            payload = json.loads(response.read(131072))
        if not isinstance(payload, dict):
            raise ValueError()
        authorized = payload.get('authorized')
        print(json.dumps({'api_reachable': True, 'authorized': authorized if isinstance(authorized, bool) else None,
                          'phone_configured': bool(payload.get('phone')),
                          'webhook_configured': bool(payload.get('webhook_url'))}))
        return 0 if authorized is True else 2
    except urllib.error.HTTPError as exc:
        print('WAPPI_HTTP_ERROR_' + str(exc.code))
    except (urllib.error.URLError, TimeoutError, OSError):
        print('WAPPI_NETWORK_UNAVAILABLE')
    except (ValueError, UnicodeError):
        print('WAPPI_INVALID_RESPONSE')
    return 1


if __name__ == '__main__':
    sys.exit(main())
