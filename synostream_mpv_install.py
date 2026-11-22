"""MPV bootstrap I/O and transactional replacement; no GUI calls."""
from urllib.parse import urlsplit
import stat
import os,re,hashlib,zipfile,tempfile,shutil,uuid
from pathlib import Path
import requests

MAX_MPV_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024

def translate_text(text): return text

def check_cancel(stop):
    if stop(): raise InterruptedError('Az MPV telepítését megszakítottad.')

def replace_install(source, destination, stop=lambda:False):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    staged=destination.with_name(destination.name+'.new-'+uuid.uuid4().hex)
    previous=destination.with_name(destination.name+'.old-'+uuid.uuid4().hex)
    moved=False
    try:
        shutil.copytree(source,staged)
        if not (staged/'mpv.exe').is_file(): raise RuntimeError('Hiányzó mpv.exe a telepítőcsomagban.')
        check_cancel(stop)
        if destination.exists():
            os.replace(destination,previous);moved=True
        try:
            os.replace(staged,destination)
        except BaseException:
            if moved: os.replace(previous,destination)
            raise
        # A locked old executable may prevent cleanup; keep the complete .old folder.
        if moved:
            try: shutil.rmtree(previous)
            except OSError: pass
        return str(destination/'mpv.exe')
    finally:
        if staged.exists(): shutil.rmtree(staged,ignore_errors=True)


def bootstrap(install_dir, release_api, max_bytes, stop, progress):
    temp_dir=tempfile.mkdtemp(prefix='synostream_mpv_')
    try:
        headers = {"User-Agent": "SynoStream-MPV-bootstrap/1.0", "Accept": "application/vnd.github+json"}
        progress.setLabelText(translate_text("MPV Windows x64 csomag keresése a hivatalos GitHub kiadások között…"))
        check_cancel(stop)
        response = requests.get(release_api, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        release = response.json()
        assets = release.get("assets", [])
    
        # Teljes Windows x64 buildet keresünk ZIP-ben, hogy a kicsomagoláshoz ne kelljen külső program.
        candidates = []
        for asset in assets:
            name = asset.get("name", "")
            low = name.lower()
            windows_build = any(marker in low for marker in (
                "w64-mingw32", "pc-windows-msvc", "windows", "win32",
            ))
            if (low.endswith(".zip") and "x86_64" in low and windows_build
                    and "mpv" in low and "libmpv" not in low and "debug" not in low):
                candidates.append(asset)
        if not candidates:
            names = ", ".join(a.get("name", "") for a in assets[:20])
            raise RuntimeError("Nem találtam letölthető Windows x64 MPV ZIP-csomagot a GitHub-kiadásban.\n" + names)
    
        # Elsőként a teljes Mingw buildet választjuk; ha ilyen nincs, az MSVC/Clang
        # Windows build is használható, amennyiben tartalmazza az mpv.exe-t.
        candidates.sort(key=lambda a: (
            "full" not in a.get("name", "").lower() and "gpl" not in a.get("name", "").lower(),
            "w64-mingw32" not in a.get("name", "").lower(),
            a.get("name", ""),
        ))
        asset = candidates[0]
        total = int(asset.get("size") or 0)
        url = asset.get("browser_download_url")
        if not url:
            raise RuntimeError("A GitHub nem adott letöltési címet az MPV-csomaghoz.")
        parsed_url = urlsplit(url)
        if (parsed_url.scheme != "https" or parsed_url.hostname != "github.com"
                or not parsed_url.path.startswith("/mpv-player/mpv/releases/download/")):
            raise RuntimeError("Az MPV-csomag letöltési címe nem a hivatalos GitHub-kiadásból származik.")
        digest_match = re.fullmatch(r"(?i)sha256:([0-9a-f]{64})", str(asset.get("digest") or ""))
        if not digest_match:
            raise RuntimeError("A GitHub-kiadás nem adott ellenőrizhető SHA-256 ujjlenyomatot az MPV-csomaghoz.")
        expected_digest = digest_match.group(1).lower()
        if total <= 0 or total > max_bytes:
            raise RuntimeError("Az MPV-csomag mérete hiányzik vagy túllépi a megengedett 512 MB-ot.")
    
        archive_path = os.path.join(temp_dir, "mpv.zip")
        progress.setLabelText(translate_text(f"MPV letöltése: {asset.get('name', 'Windows x64 build')}…"))
        progress.setValue(5)
        check_cancel(stop)
        archive_hasher = hashlib.sha256()
        with requests.get(url, headers={"User-Agent": headers["User-Agent"]}, stream=True, timeout=(15, 60)) as r:
            r.raise_for_status()
            downloaded = 0
            with open(archive_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if stop():
                        raise RuntimeError("Az MPV letöltését megszakítottad.")
                    if chunk:
                        if downloaded + len(chunk) > max_bytes:
                            raise RuntimeError("A letöltött MPV-csomag túllépte a megengedett 512 MB-ot.")
                        out.write(chunk)
                        archive_hasher.update(chunk)
                        downloaded += len(chunk)
                        if total:
                            progress.setValue(min(80, 5 + int(75 * downloaded / total)))
                            progress.setLabelText(translate_text(
                                f"MPV letöltése… {downloaded // (1024*1024)} / {max(1, total // (1024*1024))} MB"
                            ))
                            check_cancel(stop)
        if downloaded != total:
            raise RuntimeError("A letöltött MPV-csomag mérete nem egyezik a GitHub által megadottal.")
        if archive_hasher.hexdigest().lower() != expected_digest:
            raise RuntimeError("Az MPV-csomag SHA-256 ellenőrzése nem sikerült; a fájl nem lett telepítve.")
    
        progress.setLabelText(translate_text("MPV kicsomagolása…"))
        progress.setValue(85)
        check_cancel(stop)
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as zf:
            bad = zf.testzip()
            if bad:
                raise RuntimeError(f"A letöltött MPV ZIP sérült: {bad}")
            members = zf.infolist()
            if len(members) > 10000:
                raise RuntimeError("Az MPV-csomag túl sok fájlt tartalmaz.")
            uncompressed_total = 0
            for member in members:
                check_cancel(stop)
                member_name = member.filename.replace("\\", "/")
                if (member_name.startswith("/") or ":" in member_name
                        or ".." in member_name.split("/")):
                    raise RuntimeError("Az MPV-csomag nem biztonságos elérési utat tartalmaz.")
                unix_mode = member.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    raise RuntimeError("Az MPV-csomag hivatkozást tartalmaz; a kicsomagolás megszakadt.")
                if not (Path(extract_dir) / member_name).resolve().is_relative_to(Path(extract_dir).resolve()):
                    raise RuntimeError("Az MPV ZIP útvonala kilépne a célmappából.")
                uncompressed_total += member.file_size
                if uncompressed_total > MAX_MPV_EXTRACTED_BYTES:
                    raise RuntimeError("Az MPV-csomag kicsomagolt mérete túllépi a megengedett 2 GB-ot.")
            zf.extractall(extract_dir)
    
        found = None
        for root, _dirs, files in os.walk(extract_dir):
            if "mpv.exe" in [f.lower() for f in files]:
                found = os.path.join(root, next(f for f in files if f.lower() == "mpv.exe"))
                break
        if not found:
            raise RuntimeError("A csomag letöltődött, de nem található benne mpv.exe.")
    
        return replace_install(os.path.dirname(found), install_dir, stop)
    finally:
        shutil.rmtree(temp_dir,ignore_errors=True)
