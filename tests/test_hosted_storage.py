import main


def test_hosted_database_path_and_explicit_override(tmp_path, monkeypatch):
    hosted = tmp_path / 'hosted.db'
    explicit = tmp_path / 'test.db'
    monkeypatch.setenv('LOKSUTRA_DB_PATH', str(hosted))
    assert main.create_app(owner_hash='').state.db == hosted
    assert main.create_app(db_path=explicit, owner_hash='').state.db == explicit
    monkeypatch.delenv('LOKSUTRA_DB_PATH')
    assert main.create_app(owner_hash='').state.db == main.BASE / 'loksutra.db'
