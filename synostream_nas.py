"""One NAS identity over local API, DDNS HTTPS and QuickConnect fallback."""
from urllib.parse import urlsplit, urlunsplit
import json
import hashlib
import logging
import re
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


def validate_quickconnect_id(value):
    value = str(value or '').strip()
    if value and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('Érvénytelen QuickConnect-azonosító.')
    return value


def quickconnect_url(identifier, region=None):
    identifier = validate_quickconnect_id(identifier)
    if not identifier or (region is not None and not re.fullmatch(r'[a-z0-9-]+', str(region))):
        raise ValueError('Érvénytelen QuickConnect-cím vagy régió.')
    value = f"https://{identifier}{'.' + region if region else ''}.quickconnect.to"
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.username is not None or parts.password is not None
            or parts.port is not None or not parts.hostname.endswith('.quickconnect.to')
            or parts.path or parts.query or parts.fragment):
        raise ValueError('Érvénytelen QuickConnect-cím.')
    return value


def nas_json(response):
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError('A NAS nem értelmezhető JSON-választ adott.') from None
    if not isinstance(payload, (dict, list)):
        raise RuntimeError('A NAS nem értelmezhető JSON-választ adott.')
    return payload


def nas_device_key(credentials):
    identity = [str(credentials.get(k) or '').strip() for k in
                ('nas_local_url','nas_direct_url','quickconnect_id','nas_username')]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode('utf-8')).hexdigest()


def trusted_device_id(credentials):
    if credentials.get('use_device_token') is False: return ''
    try:
        value = json.loads(credentials.get('nas_device_tokens') or '{}').get(nas_device_key(credentials), '')
        return value if isinstance(value,str) and 0 < len(value) <= 4096 and not any(ord(c)<32 for c in value) else ''
    except (TypeError,ValueError,AttributeError): return ''


class NASAuthenticationError(RuntimeError):
    pass


class NASOtpRequired(NASAuthenticationError):
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
        quick = validate_quickconnect_id(self.credentials.get('quickconnect_id'))
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
                        payload = nas_json(response)
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
        identifier = validate_quickconnect_id(identifier)
        if not identifier: raise ValueError("Hiányzó QuickConnect-azonosító.")
        r = self._connect_request("post", "https://global.quickconnect.to/Serv.php", json=[
            {"version": 1, "command": "get_server_info", "stop_when_error": False,
             "stop_when_success": False, "id": "dsm_portal_https", "serverID": identifier, "is_gofile": False}
        ], timeout=(8, 15))
        r.raise_for_status()
        bases = []
        for item in nas_json(r) if isinstance(nas_json(r), list) else []:
            env = item.get("env") or {}
            if item.get("errno") == 0 and env.get("relay_region"):
                try:
                    bases.append(quickconnect_url(identifier, env['relay_region']))
                except ValueError:
                    logging.getLogger('SynoStream').warning('Érvénytelen QuickConnect-régió kihagyva: ValueError')
        last_error = None
        api_data = None
        self.session.headers.update({"User-Agent": "Mozilla/5.0 SynoStream/1.0", "Referer": quickconnect_url(identifier) + "/"})
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
        otp = self.credentials.pop("otp_code", "")
        device = trusted_device_id(self.credentials)
        trust = bool(otp and self.credentials.get('remember_device'))
        parameters = {}
        if (device or trust) and int(self.auth_version) >= 6:
            self.auth_version = 6
            parameters['device_name'] = 'SynoStream Windows'
            if device: parameters['device_id'] = device
            if trust: parameters['enable_device_token'] = 'yes'

        login=self._connect_request("post", self.auth_url, data={"api":"SYNO.API.Auth", "version":self.auth_version,
            "method":"login", "account":username, "passwd":password, "session":self.session_name, "format":"sid", **({"otp_code":otp} if otp else {}), **parameters}, timeout=(8,20), allow_redirects=False)
        try:
            login.raise_for_status(); payload=nas_json(login)
        finally:
            login.close()
        if not isinstance(payload, dict):
            raise ValueError("Érvénytelen NAS-válasz.")
        if not payload.get("success"):
            if (payload.get("error") or {}).get("code") == 403:
                raise NASOtpRequired("Kétlépcsős kód szükséges: Nyisd meg a Beállítások NAS-kapcsolatát, add meg az egyszer használatos kódot, és a háttérműveletekhez engedélyezd a megbízható eszköz megjegyzését.")
            raise NASAuthenticationError(f"NAS-bejelentkezés sikertelen (DSM-hibakód: {(payload.get('error') or {}).get('code','ismeretlen')}).")
        self.sid=(payload.get("data") or {}).get("sid", "")
        token = (payload.get("data") or {}).get("did", "")
        self.device_id = token if trust and isinstance(token,str) and 0 < len(token) <= 4096 and not any(ord(c)<32 for c in token) else ""
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
        attempts = 1 if self.transport in ('local', 'direct') or (kwargs.get('data') or {}).get('otp_code') else 3
        for attempt in range(attempts):
            self._check_cancelled()
            try:
                if self.transport in ('local', 'direct'):
                    kwargs['timeout'] = (4, 8)
                response = self._request(method, url, **kwargs)
                if response.status_code in (429, 502, 503, 504) and attempt < attempts - 1 and self.transport not in ('local', 'direct'):
                    response.close()
                    self._pause(0.5 * 2 ** attempt)
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.SSLError:
                raise RuntimeError("A NAS tanúsítványa nem ellenőrizhető. Ellenőrizd a tanúsítványt és a rendszerórát.") from None
            except (requests.ConnectionError, requests.Timeout):
                if attempt == attempts - 1:
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
                    info = getattr(self, "api_info", {}).get(api) or {}
                    endpoint = self._endpoint(info["path"]) if info.get("path") else self.list_url
                    response = self._get(endpoint, params=params, timeout=(8, 30))
                    try:
                        response.raise_for_status()
                        payload = nas_json(response)
                    finally:
                        response.close()
                    if not isinstance(payload, dict):
                        raise RuntimeError("A NAS nem értelmezhető API-választ adott.")
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
            kwargs = {"additional": '["real_path","size","owner","time","perm"]' if path else '["real_path","owner","time","perm"]', "offset": offset, "limit": 500}
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
        # Network waits and retry delays must not hold the session-state lock.
        for attempt in range(3):
            self._check_cancelled()
            with self.lock:
                url, sid, version = self.download_url, self.sid, self.download_version
            try:
                response = self._request('get', url, params={
                    "api": "SYNO.FileStation.Download", "version": version,
                    "method": "download", "path": path, "mode": "open", "_sid": sid,
                }, headers=headers or {}, stream=True, timeout=(15, 60))
                if "json" in response.headers.get("Content-Type", "").lower():
                    try:
                        code = (nas_json(response).get("error") or {}).get("code")
                    finally:
                        response.close()
                    if code in (106, 107, 119) and attempt == 0:
                        with self.lock:
                            if self.sid == sid: self.connect()
                        continue
                    raise RuntimeError("NAS-stream munkamenet- vagy jogosultsághiba (DSM: %s)." % code)
                if response.status_code in (429, 502, 503, 504) and attempt < 2:
                    response.close()
                    self._pause(0.5 * 2 ** attempt)
                    continue
                return response
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2: raise
                if self.credentials.get('nas_local_url') or self.credentials.get('nas_direct_url'):
                    with self.lock:
                        if self.sid == sid: self.connect()
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

    def delete_paths(self, paths):
        import json
        from synostream_deletion import path, blocked
        self._check_cancelled()
        values = [path(value) for value in paths]
        if not values or len(values)>64 or any(len(value.strip('/').split('/'))<2 or blocked(value) for value in values): raise ValueError('Érvénytelen törlési fájllista.')
        api = 'SYNO.FileStation.Delete'
        with self.lock:
            if api not in self.api_info:
                response=self._connect_request('get',self.base_url+'/webapi/query.cgi',params={
                    'api':'SYNO.API.Info','version':1,'method':'query','query':api},timeout=(8,15))
                try:
                    payload=nas_json(response);info=(payload.get('data') or {}).get(api)
                    if not payload.get('success') or not info:raise RuntimeError('A NAS nem támogatja a fájltörlést.')
                    self.api_info[api]=info
                finally:response.close()
            for attempt in range(2):
                self._check_cancelled()
                info=self.api_info[api]
                minimum=int(info.get('minVersion',1));maximum=int(info.get('maxVersion',0))
                if minimum<1 or maximum<minimum:raise RuntimeError('A NAS nem támogatja ezt a törlési műveletet.')
                version=max(minimum,min(2,maximum))
                try:
                    response=self._post(self._endpoint(info['path']),data={'api':api,'version':version,'method':'delete',
                        'path':json.dumps(values,ensure_ascii=False),'recursive':'false','_sid':self.sid},timeout=(8,120))
                    try:response.raise_for_status();payload=nas_json(response)
                    finally:response.close()
                except (requests.RequestException, ValueError, TypeError):
                    raise RuntimeError('A NAS-törlés eredménye nem igazolható. Frissítsd a médiatárat; nem ismételtem meg a műveletet.') from None
                if not isinstance(payload,dict):raise RuntimeError('A NAS-törlés nem adott egyértelmű visszaigazolást.')
                if payload.get('success'):
                    data=payload.get('data') or {}
                    if isinstance(data,dict) and data.get('errors'):raise RuntimeError('A NAS néhány fájlt nem tudott törölni. Frissítsd a médiatárat.')
                    return
                code=(payload.get('error') or {}).get('code')
                if code in (106,107,119) and attempt==0:
                    self.connect();continue  # Explicit rejection means the write never ran.
                raise RuntimeError('NAS-törlési hiba (DSM: %s). A műveletet nem ismételtem meg.' % code)

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
                        result=nas_json(response)
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
                    response.raise_for_status();result=nas_json(response)
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

