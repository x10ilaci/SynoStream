"""Connection settings shared by NAS transport and automatic source routing."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit


def normalize_local_url(value):
    value = str(value or '').strip()
    if not value:
        return ''
    if '://' not in value:
        value = 'http://' + value
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
        if (parsed.scheme not in ('https', 'http') or not host or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.path not in ('', '/') or any(c.isspace() for c in value)
                or any(c in value for c in ('\\', '<', '>'))):
            raise ValueError()
        if parsed.scheme == 'http':
            try:
                address = ipaddress.ip_address(host)
                allowed = address.is_private or address.is_loopback or address.is_link_local
            except ValueError:
                allowed = '.' not in host or host.endswith(('.local', '.lan'))
            if not allowed:
                raise ValueError()
        authority = parsed.netloc
        if port is None:
            authority += ':5000' if parsed.scheme == 'http' else ':5001'
        return urlunsplit((parsed.scheme, authority, '', '', ''))
    except ValueError:
        raise ValueError('Helyi NAS-címet adj meg, például https://nas.local:5001 vagy http://192.168.1.2:5000. HTTP csak helyi címhez használható.') from None


def local_nas_host(settings):
    try:
        value = normalize_local_url(settings.get('nas_local_url'))
        return urlsplit(value).hostname or ''
    except ValueError:
        return ''
