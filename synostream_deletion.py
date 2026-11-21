"""Reviewable NAS deletion plans. No deletion until the caller explicitly executes a plan."""
from dataclasses import dataclass
import json
import posixpath as pp
import re
from synostream_logic import parse_episode_position

VIDEO = {'.mkv','.mp4','.avi','.mov','.wmv','.m4v','.ts','.m2ts','.mpg','.mpeg','.webm'}
AUX = {'.nfo','.srt','.ass','.ssa','.sub','.idx','.vtt','.sup','.jpg','.jpeg','.png','.txt','.sfv','.srr','.md5','.url','.torrent','.log'}
PROTECTED = {'.synostream','#recycle','@eadir','@snapshot'}
EXTRA_DIRS = {'sample','samples','subs','subtitles','extras','proof','extrafanart'}


def path(value):
    value = str(value or '')
    if value.startswith('syno://'): value = value[7:]
    if (not value.startswith('/') or '\\' in value or any(x in ('.','..','') for x in value[1:].split('/'))
            or any(ord(x)<32 for x in value) or len(value.split('/'))<2):
        raise ValueError('Érvénytelen NAS-törlési útvonal.')
    return value


def within(value, root):
    return value == root or value.startswith(root.rstrip('/') + '/')


def video(value): return pp.splitext(value)[1].lower() in VIDEO

def sample(value): return 'sample' in value.casefold() or any(part.casefold() in {'extras','proof'} for part in pp.dirname(value).split('/'))

def blocked(value): return any(part.casefold() in PROTECTED for part in value.split('/'))

def season(value): return int(parse_episode_position(value.replace('/','\\'))[0])

def explicit_season(value):
    match=re.search(r'(?i)(?:\bS(\d{1,3})\b|season[ ._-]*(\d+)|(\d+)[ ._-]*(?:évad|evad))',pp.basename(value))
    return next((int(v) for v in match.groups() if v is not None),None) if match else None


def real_path(entry):
    value=(entry.get('additional') or {}).get('real_path') or ''
    return value if isinstance(value,str) else value.get('real_path','') if isinstance(value,dict) else ''


def stamp(entry):
    info=entry.get('additional') or {};times=info.get('time') or {}
    return (entry['path'],bool(entry.get('isdir')),int(info.get('size',entry.get('size',0)) or 0),float(times.get('mtime',0) or 0),bool(entry.get('islink')),real_path(entry))


@dataclass(frozen=True)
class Plan:
    files: tuple
    folders: tuple
    seasons: tuple
    all_seasons: bool


class Inventory:
    def __init__(self, seeds, library_roots, movie, list_folder, protected=()):
        self.library_roots=tuple(path(root.rstrip('/')) for root in library_roots)
        self.seeds=tuple(dict.fromkeys(path(seed.rstrip('/')) for seed in seeds))
        self.movie=movie;self.list_folder=list_folder
        self.protected=tuple(path(p.rstrip('/')) for p in protected if p)
        self.listings={};self.fingerprints={};self.entries={};self.roots=[]
        if not self.seeds or not self.library_roots: raise ValueError('A törléshez beállított NAS-forrásmappa szükséges.')
        for seed in self.seeds:
            if blocked(seed) or not any(within(seed, root) for root in self.library_roots):
                raise ValueError('A műsor nem a kiválasztott médiatár NAS-forrásában található.')
            if not movie and seed in self.library_roots and not video(seed):
                raise ValueError('A teljes médiatár gyökere nem törölhető műsorkártyaként.')
            root=pp.dirname(seed) if video(seed) else seed
            # Never ascend through an unrelated sibling folder or beyond a library root.
            while root not in self.library_roots:
                parent=pp.dirname(root)
                if parent in self.library_roots or not any(within(parent,r) for r in self.library_roots): break
                listing=self._list(parent)
                allowed=True
                for e in listing:
                    p=e['path']
                    if p==root:continue
                    if e.get('isdir'):
                        if pp.basename(p).casefold() not in EXTRA_DIRS and not any(within(s,p) for s in self.seeds) and (blocked(p) or self._list(p)):allowed=False;break
                    elif video(p) and p not in self.seeds and not sample(p):allowed=False;break
                    elif pp.splitext(p)[1].lower() not in AUX:allowed=False;break
                if not allowed:break
                root=parent
            self.roots.append(root)
        self.roots=tuple(r for r in dict.fromkeys(self.roots) if not any(r!=other and within(r,other) for other in self.roots))
        for root in self.roots:
            parent=pp.dirname(root)
            if any(within(parent,r) for r in self.library_roots):self._list(parent)
            self._walk(root,0,root not in self.library_roots)
        for seed in self.seeds:
            if video(seed) and seed not in self.entries:raise ValueError('A kijelölt fájl már nem található a NAS-on.')
        self.videos={p:season(p) for p,e in self.entries.items() if not e.get('isdir') and video(p) and not sample(p)
                     and (movie or any(within(p,s) if not video(s) else p==s for s in self.seeds)) and not self._protected(p)}
        if movie:
            self.targets=set(self.seeds)
        elif not self.videos:raise ValueError('A kártyához nem található törölhető epizód.')
        self.seasons=tuple(sorted(set(self.videos.values()))) if not movie else ()

    def _protected(self,p):return blocked(p) or any(within(p,root) or within(root,p) for root in self.protected)

    def _list(self, root):
        if root not in self.listings:
            listing=[];seen=set()
            for raw in self.list_folder(root):
                e=dict(raw);p=path(e.get('path') or root+'/'+e.get('name',''))
                if pp.dirname(p)!=root or p in seen:raise ValueError('A NAS nem egyértelmű mappalistát adott.')
                seen.add(p);e['path']=p
                if e.get('islink'):raise ValueError('Szimbolikus hivatkozást tartalmazó mappa nem törölhető automatikusan.')
                listing.append(e)
            self.listings[root]=listing
            self.fingerprints[root]=tuple(sorted(stamp(e) for e in listing))
        return self.listings[root]

    def _walk(self,root,depth,recursive):
        if depth>32 or len(self.entries)>20000:raise ValueError('Túl nagy törlési terület; válassz szűkebb műsorkártyát.')
        parent_entry=next((e for e in self.listings.get(pp.dirname(root),[]) if e['path']==root),{})
        physical=real_path(parent_entry).rstrip('/')
        for e in self._list(root):
            p=e['path'];resolved=real_path(e)
            if physical and resolved and pp.dirname(resolved.rstrip('/'))!=physical:
                raise ValueError('A mappa másik helyre mutató hivatkozást tartalmaz; a törlés nem indult el.')
            self.entries[p]=e
            if len(self.entries)>20000:raise ValueError('Túl nagy törlési terület.')
            if e.get('isdir') and recursive and not blocked(p):self._walk(p,depth+1,True)

    def plan(self,seasons=None):
        chosen=set(self.seasons if seasons is None else seasons)
        selected=set(self.targets) if self.movie else {p for p,s in self.videos.items() if s in chosen}
        if not selected:raise ValueError('Válassz legalább egy évadot.')
        files=set(selected)
        all_videos={p for p,e in self.entries.items() if not e.get('isdir') and video(p) and not sample(p)}
        owned=[]
        candidates=list(self.roots)+[p for p,e in self.entries.items() if e.get('isdir')]
        for directory in candidates:
            if directory in self.library_roots or blocked(directory) or self._protected(directory):continue
            descendants={p for p in all_videos if within(p,directory)}
            if descendants and descendants.issubset(selected):owned.append(directory)
        for p,e in self.entries.items():
            if e.get('isdir') or self._protected(p):continue
            if any(within(p,d) for d in owned):files.add(p);continue
            ext=pp.splitext(p)[1].lower()
            if ext in AUX:
                stem=pp.splitext(pp.basename(p))[0].casefold()
                for selected_file in selected:
                    base=pp.splitext(pp.basename(selected_file))[0].casefold()
                    if (pp.dirname(p)==pp.dirname(selected_file) or pp.basename(pp.dirname(p)).casefold() in EXTRA_DIRS) and (stem==base or stem.startswith(base+'.')):
                        files.add(p);break
                if not self.movie and pp.dirname(p) not in self.library_roots and explicit_season(p) in chosen:files.add(p)
        if any(self._protected(p) for p in files):raise ValueError('A kijelölés más médiakártya fájlját érintené.')
        folders={p for p,e in self.entries.items() if e.get("isdir") and not self._protected(p) and p not in self.library_roots and any(within(p,d) for d in owned)}
        for file in files:
            parent=pp.dirname(file)
            while parent not in self.library_roots and any(within(parent,r) for r in self.library_roots):
                folders.add(parent);parent=pp.dirname(parent)
        return Plan(tuple(sorted(files)),tuple(sorted(folders,key=lambda p:(-p.count('/'),p))),tuple(sorted(chosen)),not self.movie and chosen.issuperset(self.seasons))

    def execute(self,plan,delete_paths,progress=lambda done,total:None):
        if plan != self.plan(plan.seasons if not self.movie else None):
            raise ValueError('A törlési terv nem egyezik a jóváhagyott kijelöléssel.')
        # Validate the complete reviewed snapshot immediately before the first write.
        for directory,expected in self.listings.items():
            actual=[]
            for raw in self.list_folder(directory):
                e=dict(raw);e['path']=path(e.get('path') or directory+'/'+e.get('name',''));actual.append(stamp(e))
            if tuple(sorted(actual))!=self.fingerprints[directory]:
                raise ValueError('A NAS tartalma megváltozott. A törlési listát újra meg kell nyitni.')
        # Only the exact approved file paths are sent; recursive deletion is never used.
        for offset in range(0,len(plan.files),64):
            delete_paths(list(plan.files[offset:offset+64]));progress(min(offset+64,len(plan.files)),len(plan.files))
        removed=[]
        for directory in plan.folders:
            if not self.list_folder(directory):
                delete_paths([directory]);removed.append(directory)
        return {'files':list(plan.files),'folders':removed,'all_seasons':plan.all_seasons}
