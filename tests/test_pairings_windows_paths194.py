import os
from pathlib import Path
import pytest
import synostream_pairings as p


@pytest.mark.skipif(os.name!='nt',reason='Windows extended path spelling')
@pytest.mark.parametrize('extended_root',[False,True])
def test_extended_prefix_is_not_an_escape(tmp_path,monkeypatch,extended_root):
    root=tmp_path/'Library';root.mkdir();backend=p.LocalBackend(root)
    original=Path.resolve
    resolved=Path('\\\\?\\'+str(backend.directory))
    if extended_root:backend.root=Path('\\\\?\\'+str(root.resolve()))
    monkeypatch.setattr(Path,'resolve',lambda path,*a,**k: resolved if path==backend.directory else original(path,*a,**k))
    backend._check()
    outside=Path('\\\\?\\'+str(tmp_path/'Other/parositasok'))
    monkeypatch.setattr(Path,'resolve',lambda path,*a,**k: outside if path==backend.directory else original(path,*a,**k))
    with pytest.raises(OSError,match='kívül'):backend._check()


@pytest.mark.skipif(os.name!='nt',reason='Windows UNC spelling')
def test_extended_unc_spelling_matches_without_changing_other_devices():
    assert p._comparison_path(Path(r'\\?\UNC\server\share\Library'))==Path(r'\\server\share\Library')
    assert p._comparison_path(Path(r'\\?\Volume{example}\Library'))==Path(r'\\?\Volume{example}\Library')
