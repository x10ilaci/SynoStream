from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace
from contextlib import closing
import sqlite3
import json
import pytest
from synostream_logic import release_filename_candidate

@pytest.mark.parametrize('group',['Pirosasz','FutureUploader42','HDGirL'])
def test_repeated_release_tag_derives_candidate_without_name_list(group):
    assert release_filename_candidate(group+'-Macskak nem tancolnak.mkv','Macskak.Nem.Tancolhatnak.1997.1080p.Hun-'+group)==('Macskak nem tancolnak','1997')

def test_unmatched_tag_does_not_strip_actual_title():
    assert release_filename_candidate('Spider-Man.2002.mkv','Spider.Man.2002.1080p-TRiNiTY') is None
    assert release_filename_candidate('Pirosasz-Film.mkv','Movies') is None

def test_filename_candidate_follows_failed_folder_search(media,tmp_path,monkeypatch):
    folder=tmp_path/'Macskak.Nem.Tancolhatnak.1997.BluRay.1080p.x264.Hun-Pirosasz';folder.mkdir()
    file=folder/'Pirosasz-Macskak nem tancolnak.mkv';file.touch()
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    hit=dict(status='success',id=24662,title='A macskák nem táncolnak',overview='',date='1997',poster_url='')
    lookup=Mock(side_effect=lambda title,*a,**kw:hit if title=='Macskak nem tancolnak' else dict(status='no_result'))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        assert scanner.process_media_item(SimpleNamespace(path=str(file),name=file.name,stat=file.stat),True,db)['id']==24662
    assert [call.args[:2] for call in lookup.call_args_list]==[('Macskak Nem Tancolhatnak','1997'),('Macskak nem tancolnak','1997')]

@pytest.mark.parametrize('remote',[False,True])
def test_excluded_audio_is_not_card_or_second_movie(media,tmp_path,monkeypatch,remote):
    name='Lady.and.the.Tramp.1955.720p.BluRay.DTS.x264.HuN-TRiNiTY'
    folder=('syno:///Movies/'+name) if remote else str(tmp_path/name)
    film=folder+'/latt.720p-trinity.mkv';audio=folder+'/latt.hundub-trinity.mkv'
    if not remote:
        Path(folder).mkdir();Path(film).touch();Path(audio).touch()
    media.config['excluded_media_paths']=[media.normalize_media_path(audio)]
    scanner=media.LibraryScannerThread([],[]);scanner.get_poster=Mock(return_value=None)
    if remote:
        scanner.remote_client=Mock()
        scanner.remote_client.list_folder.return_value=[dict(name='latt.720p-trinity.mkv',path=film[7:],isdir=False),dict(name='latt.hundub-trinity.mkv',path=audio[7:],isdir=False)]
    lookup=Mock(return_value=dict(status='success',id=10340,title='Susi és Tekergő',overview='',date='1955',poster_url=''))
    monkeypatch.setattr(media,'fetch_tmdb_data',lookup)
    items=[];scanner.item_ready.connect(lambda item,movie:items.append(item))
    with closing(sqlite3.connect(media.DB_FILE)) as db:scanner.scan_folder(db,folder,True)
    assert len(items)==1 and media.normalize_media_path(items[0]['file_path'])==media.normalize_media_path(film)
    lookup.assert_called_once_with('Lady and the Tramp','1955',True)
    if not remote:assert Path(audio).exists()

def test_exclude_button_persists_and_restore_works(media,app,tmp_path,monkeypatch):
    file=tmp_path/'extra.mkv';file.touch()
    media.config.update(movies_paths=[str(tmp_path)],movies_path=str(tmp_path))
    window=media.DSVideoWindow();window.start_library_scan=Mock();monkeypatch.setattr(media,'run_worker',Mock())
    item=dict(file_path=str(file),title='Extra',id=-1,overview='',is_movie=True,library_id='movies')
    window.movies_page.add_item(item)
    def click_hide(dialog):
        button=dialog.findChild(media.QPushButton,'ExcludeMedia')
        assert button and not button.icon().isNull() and button.size().width()==26
        button.click()
        return media.QDialog.DialogCode.Accepted
    monkeypatch.setattr(media.QDialog,'exec',click_hide)
    try:
        window.open_media_detail(item)
        assert window.movies_page.count()==0 and file.exists()
        path=media.normalize_media_path(str(file))
        assert path in json.loads(Path(media.CONFIG_FILE).read_text(encoding='utf-8'))['excluded_media_paths']
        assert path in media.load_config()[0]['excluded_media_paths']
        def click_restore(dialog):
            listing=dialog.findChild(media.QListWidget);listing.selectAll()
            button=next(b for b in dialog.findChildren(media.QPushButton) if b.text()=='Kijelöltek visszaállítása')
            button.click();return media.QDialog.DialogCode.Accepted
        monkeypatch.setattr(media.QDialog,'exec',click_restore)
        window.manage_excluded_media()
        assert media.config['excluded_media_paths']==[] and file.exists()
    finally:window.close();app.processEvents()

def test_excluded_cached_card_not_loaded_on_restart(media,tmp_path):
    file=tmp_path/'hidden.mkv';file.touch();path=media.normalize_media_path(str(file))
    media.config.update(movies_paths=[str(tmp_path)],movies_path=str(tmp_path),excluded_media_paths=[path])
    with closing(sqlite3.connect(media.DB_FILE)) as db:
        db.execute('INSERT INTO library_card_cache VALUES (?,?,?)',('movies',path,json.dumps(dict(file_path=str(file),title='Hidden',id=1))));db.commit()
    window=media.DSVideoWindow()
    try:assert window._cached_page_items('movies')==[]
    finally:window.close()

def test_exclude_save_failure_preserves_card_and_config(media,app,tmp_path,monkeypatch):
    file=tmp_path/'keep.mkv';file.touch()
    window=media.DSVideoWindow();window.start_library_scan=Mock()
    item=dict(file_path=str(file),title='Keep',overview='',is_movie=True,library_id='movies')
    window.movies_page.add_item(item)
    monkeypatch.setattr(media,'save_config',Mock(return_value=(False,'test failure')))
    monkeypatch.setattr(media.QMessageBox,'warning',Mock())
    try:
        window.exclude_media_item(item)
        assert media.config['excluded_media_paths']==[] and window.movies_page.count()==1 and file.exists()
        window.start_library_scan.assert_not_called()
    finally:window.close();app.processEvents()
