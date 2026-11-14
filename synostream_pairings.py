"""Portable manual pairings: immutable, independent JSON events in each media root."""
import contextlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import sqlite3
import tempfile
import time
import threading
import uuid

SUBDIR = '.synostream/parositasok'
MAX_BYTES = 16384
NAME = re.compile(r'^[0-9a-f]{32}\.json$')


def normalize_root(path):
    if str(path).startswith('syno://'):
        return 'syno://' + posixpath.normpath('/' + str(path)[7:].replace('\\', '/').lstrip('/'))
    return os.path.normcase(os.path.abspath(path))


_case_context = threading.local()


def _logical_relative_case(root, relative):
    """Recover stored spelling without resolving media-directory junctions."""
    if relative == '.':
        return relative
    cache = getattr(_case_context, 'directories', None)
    if cache is None:
        cache = {}
    current=root
    parts=[]
    for part in relative.split('/'):
        key=normalize_root(current)
        if key not in cache:
            try:
                with os.scandir(current) as entries:
                    cache[key]={os.path.normcase(entry.name):entry.name for entry in entries}
            except OSError:
                cache[key]={}
        actual=cache[key].get(os.path.normcase(part),part)
        parts.append(actual)
        current=os.path.join(current,actual)
    return '/'.join(parts)


def relative_path(root, path):
    root, path = normalize_root(root), normalize_root(path)
    if root.startswith('syno://') != path.startswith('syno://'):
        return None
    if root.startswith('syno://'):
        if path != root and not path.startswith(root.rstrip('/') + '/'):
            return None
        relative = posixpath.relpath(path[7:], root[7:])
    else:
        try:
            if os.path.commonpath([root, path]) != root:
                return None
            relative = _logical_relative_case(root, os.path.relpath(path, root).replace('\\', '/'))
        except ValueError:
            return None
    return relative


def absolute_path(root, relative):
    if root.startswith('syno://'):
        return normalize_root('syno://' + posixpath.join(root[7:], relative))
    return normalize_root(os.path.join(root, *relative.split('/')))


def decode_event(payload, filename=None):
    if len(payload) > MAX_BYTES:
        raise ValueError('A párosítási fájl túl nagy.')
    try:
        data = json.loads(payload.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError('Érvénytelen párosítási JSON.') from error
    keys = {'format_version','event_id','relative_path','media_type','tmdb_id','title','deleted','generation','created_ns'}
    if not isinstance(data, dict) or set(data) != keys or type(data['format_version']) is not int or data['format_version'] != 1:
        raise ValueError('Ismeretlen párosítási formátum.')
    if not isinstance(data['event_id'], str) or not re.fullmatch('[0-9a-f]{32}', data['event_id']):
        raise ValueError('Érvénytelen párosításazonosító.')
    if filename is not None and filename != data['event_id'] + '.json':
        raise ValueError('Eltérő párosításazonosító.')
    rel = data['relative_path']
    if (not isinstance(rel,str) or not rel or len(rel)>2048 or '\\' in rel or ':' in rel
        or any(ord(c)<32 for c in rel) or rel.startswith('/')
        or any(part in ('','..') for part in rel.split('/'))
        or any(part.casefold()=='.synostream' for part in rel.split('/'))
        or ('.' in rel.split('/') and rel != '.')):
        raise ValueError('A párosítás útvonala nem relatív médiatári útvonal.')
    if data['media_type'] not in ('movie','tv') or (rel=='.' and data['media_type']=='movie'):
        raise ValueError('Érvénytelen médiatípus.')
    rel.encode('utf-8')
    if type(data['deleted']) is not bool or type(data['generation']) is not int or not 1<=data['generation']<=10**9:
        raise ValueError('Érvénytelen párosítási módosítás.')
    if type(data['created_ns']) is not int or data['created_ns'] < 0:
        raise ValueError('Érvénytelen időbélyeg.')
    if not isinstance(data['title'],str) or len(data['title'])>1000 or any(ord(c)<32 for c in data['title']):
        raise ValueError('Érvénytelen cím.')
    data['title'].encode('utf-8')
    if data['deleted']:
        if data['tmdb_id'] is not None:
            raise ValueError('Érvénytelen törlési bejegyzés.')
    elif type(data['tmdb_id']) is not int or not 0<data['tmdb_id']<10**10:
        raise ValueError('Érvénytelen TMDB-azonosító.')
    return data


def encode_event(event):
    payload = json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    decode_event(payload)
    return payload


def init_tables(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS portable_events(root TEXT,event_id TEXT,payload TEXT NOT NULL,PRIMARY KEY(root,event_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS portable_outbox(root TEXT,event_id TEXT,payload TEXT NOT NULL,PRIMARY KEY(root,event_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS portable_state(file_path TEXT,is_movie INTEGER,root TEXT,event_id TEXT,PRIMARY KEY(file_path,is_movie))')
    conn.execute('CREATE TABLE IF NOT EXISTS portable_event_index(root TEXT,event_id TEXT,relative_path TEXT,media_type TEXT,generation INTEGER,PRIMARY KEY(root,event_id))')
    conn.execute('CREATE INDEX IF NOT EXISTS portable_generation ON portable_event_index(root,relative_path,media_type,generation)')
    conn.execute('CREATE TABLE IF NOT EXISTS portable_file_checks(root TEXT,event_id TEXT,stamp TEXT,size INTEGER,PRIMARY KEY(root,event_id))')
    for root,identifier,payload in conn.execute('SELECT e.root,e.event_id,e.payload FROM portable_events e LEFT JOIN portable_event_index i ON e.root=i.root AND e.event_id=i.event_id WHERE i.event_id IS NULL').fetchall():
        event=json.loads(payload)
        conn.execute('INSERT INTO portable_event_index VALUES (?,?,?,?,?)',(root,identifier,event['relative_path'],event['media_type'],event['generation']))


def _store_event(conn,root,event,payload):
    conn.execute('INSERT OR IGNORE INTO portable_events VALUES (?,?,?)',(root,event['event_id'],payload))
    conn.execute('INSERT OR IGNORE INTO portable_event_index VALUES (?,?,?,?,?)',(root,event['event_id'],event['relative_path'],event['media_type'],event['generation']))



def enqueue(conn, roots, path, is_movie, tmdb_id=None, title='', deleted=False):
    """Called in the same transaction as the local manual override edit."""
    candidates = [(normalize_root(root),relative_path(root,path)) for root in roots]
    candidates = [(root,rel) for root,rel in candidates if rel is not None]
    if not candidates:
        return None
    root,rel = max(candidates,key=lambda item:len(item[0]))
    previous = conn.execute('SELECT e.payload FROM portable_state s JOIN portable_events e ON e.root=s.root AND e.event_id=s.event_id WHERE s.file_path=? AND s.is_movie=? AND s.root=?', (normalize_root(path),int(is_movie),root)).fetchone()
    if previous:
        rel=json.loads(previous[0])['relative_path']
    generation=conn.execute('SELECT COALESCE(MAX(generation),0) FROM portable_event_index WHERE root=? AND relative_path=? AND media_type=?',(root,rel,'movie' if is_movie else 'tv')).fetchone()[0]+1
    event=dict(format_version=1,event_id=uuid.uuid4().hex,relative_path=rel,media_type='movie' if is_movie else 'tv',tmdb_id=None if deleted else int(tmdb_id),title='' if deleted else str(title),deleted=bool(deleted),generation=generation,created_ns=time.time_ns())
    payload=encode_event(event).decode('utf-8')
    _store_event(conn,root,event,payload)
    conn.execute('INSERT INTO portable_outbox VALUES (?,?,?)',(root,event['event_id'],payload))
    conn.execute('INSERT OR REPLACE INTO portable_state VALUES (?,?,?,?)',(normalize_root(path),int(is_movie),root,event['event_id']))
    return event


def _comparison_path(path):
    # Windows realpath can retain the extended prefix if another process
    # creates a missing parent while it is resolving the path. Normalize only
    # the comparison spelling; retain extended paths for filesystem access.
    value = str(path)
    if os.name == 'nt':
        if value[:8].lower() == '\\\\?\\unc\\':
            value = '\\\\' + value[8:]
        elif value.startswith('\\\\?\\') and re.match(r'^[A-Za-z]:\\', value[4:]):
            value = value[4:]
    return Path(value)


class LocalBackend:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.directory=self.root / '.synostream' / 'parositasok'

    def _check(self):
        for path in (self.root/'.synostream',self.directory):
            if path.is_symlink() or path.is_junction():
                raise OSError('A párosítási mappa nem lehet átirányítás.')
        if not _comparison_path(self.directory.resolve()).is_relative_to(_comparison_path(self.root)):
            raise OSError('A párosítási mappa kívül esik a médiatáron.')

    def list_names(self):
        self._check()
        if not self.root.is_dir():
            raise OSError('A médiatár nem érhető el.')
        if not self.directory.exists():return []
        with os.scandir(self.directory) as entries:
            names=[]
            self.fingerprints={}
            for entry in entries:
                if NAME.fullmatch(entry.name) and entry.is_file(follow_symlinks=False):
                    names.append(entry.name)
                    info=entry.stat(follow_symlinks=False)
                    self.fingerprints[entry.name]=(str(info.st_mtime_ns),info.st_size)
        return names

    def read(self,name):
        self._check()
        if not NAME.fullmatch(name):raise ValueError('Érvénytelen fájlnév.')
        target=self.directory/name
        if target.is_symlink():raise OSError('Átirányított párosítási fájl.')
        with target.open('rb') as f:return f.read(MAX_BYTES+1)

    def write(self,name,payload):
        self._check();decode_event(payload,name)
        self.directory.mkdir(parents=True,exist_ok=True)
        target=self.directory/name
        if target.exists():
            if self.read(name)!=payload:raise OSError('Eltérő tartalmú párosításazonosító.')
            return
        fd,temporary=tempfile.mkstemp(prefix='.',suffix='.tmp',dir=self.directory)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
            try:os.rename(temporary,target)
            except FileExistsError:
                if self.read(name)!=payload:raise
        finally:
            with contextlib.suppress(FileNotFoundError):os.remove(temporary)

    def repair(self,name,payload):
        self._check();decode_event(payload,name)
        target=self.directory/name
        if target.exists():
            current=self.read(name)
            if current==payload:return
            try:
                decode_event(current,name)
            except (ValueError,UnicodeError):
                quarantine=self.directory/('.corrupt-'+name+'-'+uuid.uuid4().hex+'.bak')
                os.rename(target,quarantine)
            else:
                raise OSError('Érvényes, de eltérő párosítás automatikusan nem írható felül.')
        self.write(name,payload)
        if self.read(name)!=payload:raise OSError('A párosítás helyreállítása nem igazolható.')



class NASBackend:
    def __init__(self,root,client,root_listing=None):
        self.root=normalize_root(root)[7:]
        self.directory=self.root.rstrip('/')+'/'+SUBDIR
        self.client=client
        self.root_listing=root_listing

    def list_names(self):
        listing=self.root_listing
        if listing is None:listing=self.client.list_folder(self.root)
        if not any(item.get('name')=='.synostream' and item.get('isdir') for item in listing):return []
        intermediate=self.client.list_folder(self.root.rstrip('/')+'/.synostream')
        if not any(item.get('name')=='parositasok' and item.get('isdir') for item in intermediate):return []

        listing=self.client.list_folder(self.directory)
        names=[item['name'] for item in listing
               if isinstance(item.get('name'),str) and NAME.fullmatch(item['name']) and not item.get('isdir')]
        self.fingerprints={}
        name_set=set(names)
        for item in listing:
            if item.get('name') not in name_set:continue
            additional=item.get('additional') or {}
            stamp=(additional.get('time') or {}).get('mtime',0)
            size=additional.get('size',item.get('size',0))
            if isinstance(stamp,(int,float)) and stamp>0 and type(size) is int and size>0:
                self.fingerprints[item['name']]=(str(stamp),size)
        return names

    def read(self,name):
        if not NAME.fullmatch(name):raise ValueError('Érvénytelen fájlnév.')
        return self.client.read_pairing(self.directory+'/'+name)

    def write(self,name,payload):
        decode_event(payload,name)
        self.client.upload_pairing(self.directory,name,payload)
        # A completed upload is acknowledged only after a matching readback.
        if self.read(name)!=payload:raise OSError('A NAS nem igazolta vissza a párosítás mentését.')

    def repair(self,name,payload):
        self.write(name,payload)



def synchronize(conn,root,backend,should_stop=lambda:False,all_roots=None,verify=False,defer_paths=()):
    previous=getattr(_case_context,'directories',None)
    _case_context.directories={}
    try:
        return _synchronize(conn,root,backend,should_stop,all_roots,verify,defer_paths)
    finally:
        _case_context.directories=previous


def _synchronize(conn,root,backend,should_stop,all_roots,verify,defer_paths=()):
    """Import -> preserve/migrate local choices -> publish outbox -> apply winners."""
    root=normalize_root(root)
    stats=dict(imported=0,written=0,pending=0,invalid=0,repaired=0,warnings=[])
    def stop():
        if should_stop():raise InterruptedError('A párosítások szinkronizálása megszakítva.')
    names=backend.list_names()
    known={row[0]:row[1] for row in conn.execute('SELECT event_id,payload FROM portable_events WHERE root=?',(root,))}
    checks={row[0]:(row[1],row[2]) for row in conn.execute('SELECT event_id,stamp,size FROM portable_file_checks WHERE root=?',(root,))}
    fingerprints=getattr(backend,'fingerprints',{})
    if not isinstance(fingerprints,dict):fingerprints={}
    repair_ids=set()
    blocked_ids=set()
    def invalid_record(name):
        stats['invalid']+=1
        identifier=name[:-5]
        with conn:
            conn.execute('DELETE FROM portable_file_checks WHERE root=? AND event_id=?',(root,identifier))
            if identifier in known:
                conn.execute('INSERT OR REPLACE INTO portable_outbox VALUES (?,?,?)',(root,identifier,known[identifier]))
                repair_ids.add(identifier)
    read_failures=0
    for name in names:
        stop()
        identifier=name[:-5]
        if identifier in known and not verify and fingerprints.get(name) is not None and checks.get(identifier)==fingerprints[name]:
            continue
        try:
            payload=backend.read(name)
            read_failures=0
        except InterruptedError:raise
        except ValueError:
            invalid_record(name)
            continue
        except Exception:
            stats['invalid']+=1
            read_failures+=1
            if read_failures>=3:
                stats['warnings'].append('A közös párosítások olvasását ismétlődő elérési hiba miatt megszakítottam.')
                break
            continue
        try:
            event=decode_event(payload,name)
            canonical=encode_event(event).decode('utf-8')
        except (ValueError,TypeError,UnicodeError):
            invalid_record(name)
            continue
        if identifier in known and event != json.loads(known[identifier]):
            blocked_ids.add(identifier)
            stats['invalid']+=1
            stats['warnings'].append('Egy meglévő párosítás tartalma azonos azonosító mellett megváltozott; nem írtam felül automatikusan.')
            with conn:conn.execute('DELETE FROM portable_file_checks WHERE root=? AND event_id=?',(root,identifier))
            continue
        with conn:
            _store_event(conn,root,event,canonical)
            if fingerprints.get(name) is not None:
                stamp,size=fingerprints[name]
                conn.execute('INSERT OR REPLACE INTO portable_file_checks VALUES (?,?,?,?)',(root,identifier,stamp,size))
    # Seed existing manually entered choices, but never repeatedly resurrect removals.
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        legacy_winners={}
        for payload, in conn.execute('SELECT payload FROM portable_events WHERE root=?',(root,)):
            item=json.loads(payload);key=(item['relative_path'],item['media_type'])
            if key not in legacy_winners or (item['generation'],item['event_id'])>(legacy_winners[key]['generation'],legacy_winners[key]['event_id']):
                legacy_winners[key]=item
        for path,identifier,title,is_movie in conn.execute('SELECT file_path,tmdb_id,custom_title,is_movie FROM manual_overrides').fetchall():
            stop()
            if normalize_root(path) in defer_paths:continue
            if relative_path(root,path) is None:continue
            if all_roots:
                candidates=[normalize_root(candidate) for candidate in all_roots if relative_path(candidate,path) is not None]
                if candidates and max(candidates,key=len)!=root:continue
            state=conn.execute('SELECT root FROM portable_state WHERE file_path=? AND is_movie=?',(normalize_root(path),int(bool(is_movie)))).fetchone()
            if (state is None or state[0]!=root) and type(identifier) is int and identifier>0:
                # If another PC already publishes exactly this choice, simply adopt it.
                winner=legacy_winners.get((relative_path(root,path),'movie' if is_movie else 'tv'))
                if winner and not winner['deleted'] and winner['tmdb_id']==identifier and winner['title']==(title or ''):
                    conn.execute('INSERT OR REPLACE INTO portable_state VALUES (?,?,?,?)',(normalize_root(path),int(bool(is_movie)),root,winner['event_id']))
                else:
                    try:enqueue(conn,[root],path,bool(is_movie),identifier,title or '')
                    except (ValueError,OSError):
                        stats['invalid']+=1
                        stats['warnings'].append('Egy helyi párosítást nem lehetett hordozható formában menteni; a többi mentése folytatódik.')
    # If the shared directory was lost, local immutable history can restore it.
    present = {name[:-5] for name in names}
    with conn:
        for identifier,payload in conn.execute('SELECT event_id,payload FROM portable_events WHERE root=?',(root,)).fetchall():
            if identifier not in present:
                conn.execute('INSERT OR IGNORE INTO portable_outbox VALUES (?,?,?)',(root,identifier,payload))
    for event_id,payload in conn.execute('SELECT event_id,payload FROM portable_outbox WHERE root=?',(root,)).fetchall():
        stop()
        if event_id in blocked_ids:
            continue
        try:
            if event_id in repair_ids:
                backend.repair(event_id+'.json',payload.encode('utf-8'))
                stats['repaired']+=1
            else:backend.write(event_id+'.json',payload.encode('utf-8'))
        except InterruptedError:raise
        except Exception:
            stats['warnings'].append('A médiatári párosítás mentése nem sikerült; helyben megmaradt, később újrapróbálható.')
            break
        with conn:conn.execute('DELETE FROM portable_outbox WHERE root=? AND event_id=?',(root,event_id))
        stats['written']+=1
    winners={}
    for payload, in conn.execute('SELECT payload FROM portable_events WHERE root=?',(root,)):
        event=json.loads(payload);key=(event['relative_path'],event['media_type'])
        if key not in winners or (event['generation'],event['event_id'])>(winners[key]['generation'],winners[key]['event_id']):winners[key]=event
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        # Read again under the write transaction so a concurrent GUI edit wins too.
        for payload, in conn.execute('SELECT payload FROM portable_events WHERE root=?',(root,)):
            event=json.loads(payload);key=(event['relative_path'],event['media_type'])
            if key not in winners or (event['generation'],event['event_id'])>(winners[key]['generation'],winners[key]['event_id']):winners[key]=event
        for event in winners.values():
            stop();path=absolute_path(root,event['relative_path']);flag=int(event['media_type']=='movie')
            state=conn.execute('SELECT event_id FROM portable_state WHERE file_path=? AND is_movie=?',(path,flag)).fetchone()
            current=conn.execute('SELECT tmdb_id,custom_title,is_movie FROM manual_overrides WHERE file_path=?',(path,)).fetchone()
            if event['deleted']:
                if current and int(bool(current[2]))==flag:
                    conn.execute('DELETE FROM manual_overrides WHERE file_path=?',(path,))
                    conn.execute("DELETE FROM media_cache WHERE file_path=? AND signature LIKE 'override:%'",(path,))
                    stats['imported']+=1
            elif current is None or (current[0],current[1] or '',int(bool(current[2])))!=(event['tmdb_id'],event['title'],flag):
                conn.execute('INSERT OR REPLACE INTO manual_overrides(file_path,tmdb_id,custom_title,is_movie) VALUES (?,?,?,?)',(path,event['tmdb_id'],event['title'],flag))
                conn.execute('DELETE FROM media_cache WHERE file_path=?',(path,))
                stats['imported']+=1
            conn.execute('INSERT OR REPLACE INTO portable_state VALUES (?,?,?,?)',(path,flag,root,event['event_id']))
    stats['pending']=conn.execute('SELECT COUNT(*) FROM portable_outbox WHERE root=?',(root,)).fetchone()[0]
    if stats['invalid']>stats['repaired']:stats['warnings'].append('Néhány sérült vagy nem olvasható párosítási fájlt kihagytam.')
    return stats
