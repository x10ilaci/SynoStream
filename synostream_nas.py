"""One NAS identity over local API, DDNS HTTPS and QuickConnect fallback."""
from urllib.parse import urlsplit, urlunsplit
import threading
import time
import requests
from synostream_connections import normalize_local_url

def normalize_direct_url(value):
    value = (value or '').strip()
    if not value:
        return ''
    if '://' not in value:
        value = 'https://' + value
    try:
        parts = urlsplit(value)
        port = parts.port
        if (parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.query or parts.fragment
                or parts.path not in ('', '/') or any(c.isspace() for c in value)
                or any(c in value for c in ('\\', '<', '>'))):
            raise ValueError()
    except ValueError:
        raise ValueError('Érvényes HTTP- vagy HTTPS-címet adj meg, útvonal és belépési adatok nélkül (pl. https://nas.pelda.hu:5001).') from None
    return urlunsplit((parts.scheme, parts.netloc, '', '', ''))


class NASAuthenticationError(RuntimeError):
    pass


class RemoteNASClient:
    """One File Station identity over local network, DDNS or QuickConnect."""
    def __init__(self, credentials, should_stop=None, session_name="FileStation", extra_apis=()):
        self.session_name = session_name
        self.extra_apis = tuple(extra_apis)
        self.api_info = {}
        self.transport = "quickconnect"
        self.credentials = dict(credentials)
        self.should_stop = should_stop or (lambda: False)
        self.lock = threading.RLock()
        self.session = requests.Session()
        self.base_url = ""
        self.sid = ""
        self.auth_url = ""
        self.auth_version = 6
        self.list_url = ""
        self.list_version = 2
        self.download_url = ""
        self.download_version = 2
        try:
            self.connect()
        except Exception:
            self.session.close()
            raise

    def connect(self):
        self._check_cancelled()
        username = str(self.credentials.get('nas_username') or '').strip()
        password = self.credentials.get('nas_password') or ''
        local = normalize_local_url(self.credentials.get('nas_local_url'))
        direct = normalize_direct_url(self.credentials.get('nas_direct_url'))
        quick = str(self.credentials.get('quickconnect_id') or '').strip()
        if not username or not password or not (local or direct or quick):
            raise RuntimeError('A NAS-kapcsolatnál adj meg legalább egy címet, felhasználónevet és jelszót.')
        routes = [('local', local), ('direct', direct), ('quickconnect', quick)]
        for route, address in routes:
            if not address:
                continue
            self._check_cancelled()
            self.transport = route
            self.sid = ''
            self.api_info = {}
            self.session.headers.pop('Referer', None)
            cookies = getattr(self.session, 'cookies', None)
            if cookies is not None:
                cookies.clear()
            try:
                if route == 'quickconnect':
                    info = self._discover_quickconnect(address)
                else:
                    self.base_url = address
                    response = self._get(address + '/webapi/query.cgi', params={
                        'api':'SYNO.API.Info', 'version':1, 'method':'query',
                        'query':','.join(('SYNO.API.Auth','SYNO.FileStation.List','SYNO.FileStation.Download') + self.extra_apis)
                    }, timeout=(2, 4) if route == 'local' else (3, 5))
                    try:
                        response.raise_for_status()
                        payload = response.json()
                        info = payload.get('data') if isinstance(payload, dict) and payload.get('success') else None
                        if not isinstance(info, dict) or not all(isinstance(info.get(k), dict) and info[k] for k in
                                ('SYNO.API.Auth','SYNO.FileStation.List','SYNO.FileStation.Download')):
                            raise ValueError('Hiányos NAS API-válasz.')
                    finally:
                        response.close()
                self._login_from_info(info, username, password)
                return
            except (InterruptedError, NASAuthenticationError):
                raise
            except (requests.RequestException, RuntimeError, ValueError, TypeError, KeyError):
                self.sid = ''
                continue
        raise RuntimeError('A NAS egyik beállított elérésen sem érhető el. Ellenőrizd a címeket, a hálózatot és a tanúsítványt.') from None

    def _discover_quickconnect(self, identifier):
        r = self._connect_request("post", "https://global.quickconnect.to/Serv.php", json=[
            {"version": 1, "command": "get_server_info", "stop_when_error": False,
             "stop_when_success": False, "id": "dsm_portal_https", "serverID": identifier, "is_gofile": False}
        ], timeout=(8, 15))
        r.raise_for_status()
        bases = []
        for item in r.json() if isinstance(r.json(), list) else []:
            env = item.get("env") or {}
            if item.get("errno") == 0 and env.get("relay_region"):
                bases.append(f"https://{identifier}.{env['relay_region']}.quickconnect.to")
        last_error = None
        api_data = None
        self.session.headers.update({"User-Agent": "Mozilla/5.0 SynoStream/1.0", "Referer": f"https://{identifier}.quickconnect.to/"})
        for base in dict.fromkeys(bases):
            try:
                self._connect_request("get", base, timeout=(8, 15)).raise_for_status()
                q = self._connect_request("get", base + "/webapi/query.cgi", params={"api":"SYNO.API.Info", "version":1,
                    "method":"query", "query":",".join(("SYNO.API.Auth", "SYNO.FileStation.List", "SYNO.FileStation.Download") + self.extra_apis)}, timeout=(8, 15))
                q.raise_for_status(); data=q.json()
                if data.get("success"):
                    self.base_url=base; api_data=data["data"]; break
            except InterruptedError:
                raise
            except Exception as exc:
                last_error=exc
        if not api_data:
            raise RuntimeError(f"A QuickConnect API nem érhető el: {last_error or 'nincs közvetítői cím'}")
        return api_data

    def _login_from_info(self, info, username, password):
        self.api_info = info
        auth=info.get("SYNO.API.Auth") or {}
        self.auth_url=self._endpoint(auth.get("path") or "auth.cgi")
        self.auth_version=auth.get("maxVersion") or 6
        login=self._connect_request("post", self.auth_url, data={"api":"SYNO.API.Auth", "version":self.auth_version,
            "method":"login", "account":username, "passwd":password, "session":self.session_name, "format":"sid"}, timeout=(8,20))
        try:
            login.raise_for_status(); payload=login.json()
        finally:
            login.close()
        if not isinstance(payload, dict):
            raise ValueError("Érvénytelen NAS-válasz.")
        if not payload.get("success"):
            raise NASAuthenticationError(f"NAS-bejelentkezés sikertelen (DSM-hibakód: {(payload.get('error') or {}).get('code','ismeretlen')}).")
        self.sid=(payload.get("data") or {}).get("sid", "")
        li=info.get("SYNO.FileStation.List") or {}; dl=info.get("SYNO.FileStation.Download") or {}
        self.list_version=li.get("maxVersion") or 2
        self.list_url=self._endpoint(li.get("path") or "entry.cgi")
        self.download_version=dl.get("maxVersion") or 2
        self.download_url=self._endpoint(dl.get("path") or "entry.cgi")
        if not self.sid:
            raise RuntimeError("A NAS nem adott érvényes munkamenet-azonosítót.")

    def _endpoint(self, path):
        if not isinstance(path, str) or path.startswith('/') or any(c in path for c in ('..', ':', '?', '#', '\\')):
            raise ValueError('Érvénytelen NAS API-útvonal.')
        return self.base_url.rstrip('/') + '/webapi/' + path

    def _request(self, method, url, **kwargs):
        if getattr(self, 'transport', '') in ('local', 'direct'):
            kwargs['allow_redirects'] = False
        response = getattr(self.session, method)(url, **kwargs)
        if getattr(self, 'transport', '') in ('local', 'direct') and 300 <= response.status_code < 400:
            response.close()
            raise RuntimeError('A közvetlen NAS-cím átirányítást adott. A végleges HTTP-/HTTPS-címet add meg.')
        return response

    def _get(self, url, **kwargs):
        try:
            return self._request('get', url, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            params = kwargs.get('params') or {}
            if (not self.sid or params.get('method') == 'logout'
                    or not (self.credentials.get('nas_local_url') or self.credentials.get('nas_direct_url'))):
                raise
            # Safe reads can change route before any bytes reach the caller.
            # Never replay POSTs: a torrent/upload may already have been accepted.
            old_base = self.base_url.rstrip('/')
            self.connect()
            if not url.startswith(old_base + '/'):
                raise RuntimeError('A NAS-kérés nem a kiválasztott kapcsolathoz tartozik.') from None
            api = params.get('api')
            info = self.api_info.get(api) or {}
            endpoint = self._endpoint(info['path']) if info.get('path') else self.base_url.rstrip('/') + url[len(old_base):]
            if '_sid' in params:
                kwargs['params'] = dict(params, _sid=self.sid)
            return self._request('get', endpoint, **kwargs)

    def _post(self, url, **kwargs):
        return self._request('post', url, **kwargs)

    def _connect_request(self, method, url, **kwargs):
        for attempt in range(1 if self.transport in ('local', 'direct') else 3):
            self._check_cancelled()
            try:
                if self.transport in ('local', 'direct'):
                    kwargs['timeout'] = (4, 8)
                response = self._request(method, url, **kwargs)
                if response.status_code in (429, 502, 503, 504) and attempt < 2 and self.transport not in ('local', 'direct'):
                    response.close()
                    self._pause(0.5 * 2 ** attempt)
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.SSLError:
                raise RuntimeError("A NAS tanúsítványa nem ellenőrizhető. Ellenőrizd a tanúsítványt és a rendszerórát.") from None
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2 or self.transport in ('local', 'direct'):
                    raise RuntimeError("A NAS nem érhető el. Ellenőrizd az internetkapcsolatot és a QuickConnect-azonosítót.") from None
                self._pause(0.5 * 2 ** attempt)

    def _check_cancelled(self):
        if self.should_stop():
            raise InterruptedError("Megszakítva")

    def _pause(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._check_cancelled()
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))

    def api_get(self, api, version, method, **kwargs):
        # Serialize requests and session renewal; never repeat state-changing calls.
        with self.lock:
            renewed = False
            for attempt in range(3):
                self._check_cancelled()
                try:
                    params = dict(api=api, version=version, method=method, _sid=self.sid, **kwargs)
                    response = self._get(self.list_url, params=params, timeout=(8, 30))
                    try:
                        response.raise_for_status()
                        payload = response.json()
                    finally:
                        response.close()
                    if payload.get("success"):
                        return payload.get("data") or {}
                    code = (payload.get("error") or {}).get("code")
                    if code in (106, 107, 119) and not renewed:
                        self.connect()
                        renewed = True
                        continue
                    raise RuntimeError("NAS-jogosultság vagy munkamenethiba (DSM: %s)." % code)
                except (requests.ConnectionError, requests.Timeout):
                    if attempt == 2:
                        raise RuntimeError("A NAS nem érhető el. Ellenőrizd a hálózatot, majd próbáld újra.") from None
                    self._pause(0.5 * 2 ** attempt)
                except requests.HTTPError as exc:
                    if exc.response.status_code not in (429, 502, 503, 504) or attempt == 2:
                        raise
                    self._pause(0.5 * 2 ** attempt)
            raise RuntimeError("A NAS-művelet nem sikerült az újrapróbálkozások után.")

    def list_folder(self, path):
        entries = []
        seen = set()
        offset = 0
        while True:
            self._check_cancelled()
            kwargs = {"additional": "real_path,size,owner,time,perm", "offset": offset, "limit": 500}
            if path:
                kwargs["folder_path"] = path
            data = self.api_get("SYNO.FileStation.List", self.list_version,
                                "list" if path else "list_share", **kwargs)
            batch = data.get("files" if path else "shares") or []
            if not isinstance(batch, list):
                raise RuntimeError("A NAS mappalistája nem értelmezhető.")
            for item in batch:
                if not isinstance(item, dict):
                    raise RuntimeError("A NAS mappalistája nem értelmezhető.")
                identity = item.get("path") or item.get("name")
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise RuntimeError("A NAS ismétlődő vagy érvénytelen mappalistát adott.")
                seen.add(identity)
            entries.extend(batch)
            offset += len(batch)
            total = data.get("total")
            if not batch and total is not None and offset < int(total):
                raise RuntimeError("A NAS hiányos mappalistát adott; a korábbi lista megmarad.")
            if not batch or (total is not None and offset >= int(total)) or (total is None and len(batch) < 500):
                return entries

    def open_stream(self, path, headers=None):
        # Retry only before forwarding bytes. MPV handles recovery of an interrupted body.
        with self.lock:
            for attempt in range(3):
                try:
                    response = self._get(self.download_url, params={
                        "api": "SYNO.FileStation.Download", "version": self.download_version,
                        "method": "download", "path": path, "mode": "open", "_sid": self.sid,
                    }, headers=headers or {}, stream=True, timeout=(15, 60))
                    if "json" in response.headers.get("Content-Type", "").lower():
                        try:
                            code = (response.json().get("error") or {}).get("code")
                        finally:
                            response.close()
                        if code in (106, 107, 119) and attempt == 0:
                            self.connect()
                            continue
                        raise RuntimeError("NAS-stream munkamenet- vagy jogosultsághiba (DSM: %s)." % code)
                    if response.status_code in (429, 502, 503, 504) and attempt < 2:
                        response.close()
                        self._pause(0.5 * 2 ** attempt)
                        continue
                    return response
                except (requests.ConnectionError, requests.Timeout):
                    if attempt == 2:
                        raise
                    self._pause(0.5 * 2 ** attempt)

    def read_pairing(self, path):
        """Read bounded JSON file content, distinct from JSON API error envelopes."""
        import json
        import re
        if not re.search(r"/\.synostream/parositasok/[0-9a-f]{32}\.json$", path):
            raise ValueError("Érvénytelen hordozható párosítási útvonal.")
        with self.lock:
            for attempt in range(2):
                self._check_cancelled()
                response=self._get(self.download_url,params={"api":"SYNO.FileStation.Download",
                    "version":self.download_version,"method":"download","path":path,"mode":"download","_sid":self.sid},
                    stream=True,timeout=(8,30))
                try:
                    response.raise_for_status();content=bytearray()
                    for chunk in response.iter_content(16384):
                        self._check_cancelled();content.extend(chunk)
                        if len(content)>16384:raise ValueError("A párosítási fájl túl nagy.")
                finally:response.close()
                try:data=json.loads(bytes(content).decode('utf-8'))
                except (ValueError,UnicodeError,RecursionError):return bytes(content)
                if isinstance(data,dict) and data.get('success') is False and 'error' in data:
                    code=(data.get('error') or {}).get('code')
                    if code in (106,107,119) and attempt==0:
                        self.connect();continue
                    raise RuntimeError(f"A párosítás nem olvasható a NAS-ról (DSM: {code}).")
                return bytes(content)

    def upload_pairing(self, directory, name, payload):
        """Publish one private UUID event; an uncertain write is retried only later."""
        import re
        if not re.fullmatch(r"[0-9a-f]{32}\.json", name) or len(payload) > 16384 or not directory.endswith('/.synostream/parositasok'):
            raise ValueError("Érvénytelen hordozható párosítási cél.")
        api = "SYNO.FileStation.Upload"
        with self.lock:
            for attempt in range(2):
                self._check_cancelled()
                info = self.api_info.get(api)
                if not info:
                    response = self._connect_request("get", self.base_url.rstrip('/') + '/webapi/query.cgi',
                        params={"api":"SYNO.API.Info","version":1,"method":"query","query":api},timeout=(8,15))
                    try:
                        response.raise_for_status()
                        result=response.json()
                        info=(result.get('data') or {}).get(api) if result.get('success') else None
                    finally:response.close()
                    if info:self.api_info[api]=info
                if not info or int(info.get('minVersion',1))>2 or int(info.get('maxVersion',0))<2:
                    raise RuntimeError("A NAS nem támogatja a párosítások mentését ezen a kapcsolaton.")
                endpoint=self.base_url.rstrip('/')+'/webapi/'+info['path'].lstrip('/')
                # Parameters precede the multipart file, as required by File Station.
                # A UUID belongs to this immutable event. Replacing the same UUID
                # repairs an interrupted upload without touching another edit.
                response=self._post(endpoint,data={"api":api,"version":2,"method":"upload","_sid":self.sid,
                    "path":directory,"create_parents":"true","overwrite":"true"},
                    files={"file":(name,payload,"application/json")},timeout=(8,45))
                try:
                    response.raise_for_status();result=response.json()
                finally:response.close()
                if result.get('success'):return
                code=(result.get('error') or {}).get('code')
                if code in (106,107,119) and attempt==0:
                    self.connect();continue
                raise RuntimeError(f"A NAS nem tudta elmenteni a párosítást (DSM: {code}).")

    def close(self):
        if self.sid and self.auth_url:
            try: self._get(self.auth_url, params={"api":"SYNO.API.Auth","version":self.auth_version,"method":"logout","session":self.session_name,"_sid":self.sid}, timeout=(2,3))
            except requests.RequestException: pass
        self.session.close()

