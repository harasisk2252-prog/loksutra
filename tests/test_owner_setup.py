"""Owner setup tests use only temporary .env files and generated test-only passwords."""
import secrets
import tkinter as tk
from pathlib import Path
import pytest
from dotenv import dotenv_values
import setup_owner
from owner_auth import password_matches, valid_hash

def sample_password():
    return secrets.token_urlsafe(24)

@pytest.mark.parametrize("password,confirmation", [("short","short"),(" "*12," "*12),("a"*257,"a"*257),("a"*12,"b"*12)])
def test_invalid_input_does_not_change_env(tmp_path,password,confirmation):
    target=tmp_path/".env"
    target.write_text("GNANI_API_KEY=test-only-placeholder\n",encoding="utf-8")
    before=target.read_bytes()
    with pytest.raises(ValueError):
        setup_owner.save_owner_password(password,confirmation,target)
    assert target.read_bytes()==before

def test_save_hash_preserves_configuration(tmp_path,capsys):
    target=tmp_path/".env"
    target.write_text("# Keep this comment\nGNANI_API_KEY=test-only-placeholder\nAPP_ENV=development\n",encoding="utf-8")
    password=sample_password()
    setup_owner.save_owner_password(password,password,target)
    result=dotenv_values(target)
    assert result["GNANI_API_KEY"]=="test-only-placeholder"
    assert result["APP_ENV"]=="development"
    assert "# Keep this comment" in target.read_text()
    assert valid_hash(result["OWNER_PASSWORD_HASH"])
    assert password_matches(password,result["OWNER_PASSWORD_HASH"])
    assert password not in target.read_text()
    assert not capsys.readouterr().out

def test_path_independent_of_working_directory(tmp_path,monkeypatch):
    project=tmp_path/"Project with spaces";project.mkdir()
    other=tmp_path/"elsewhere";other.mkdir()
    monkeypatch.setattr(setup_owner,"BASE",project)
    monkeypatch.chdir(other)
    password=sample_password()
    setup_owner.save_owner_password(password,password)
    assert (project/".env").is_file()
    assert not (other/".env").exists()

def test_gui_masking_retry_and_success(tmp_path,monkeypatch):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox,"showinfo",lambda *args,**kwargs:None)
    root=tk.Tk();root.withdraw()
    target=tmp_path/".env"
    dialog=setup_owner.OwnerPasswordDialog(root,target)
    assert dialog.first.cget("show")=="*" and dialog.second.cget("show")=="*"
    password=sample_password()
    dialog.password.set(password);dialog.confirmation.set("different")
    dialog.save()
    assert not target.exists() and not dialog.saved
    assert "do not match" in dialog.status.get()
    assert dialog.password.get()==password
    assert dialog.confirmation.get()==""
    dialog.confirmation.set(password)
    dialog.save()
    assert dialog.saved
    assert password_matches(password,dotenv_values(target)["OWNER_PASSWORD_HASH"])

def test_gui_cancel_writes_nothing(tmp_path):
    root=tk.Tk();root.withdraw()
    target=tmp_path/".env"
    dialog=setup_owner.OwnerPasswordDialog(root,target)
    dialog.password.set(sample_password())
    dialog.cancel()
    assert not dialog.saved and not target.exists()

def test_failed_write_keeps_dialog_available(tmp_path,monkeypatch):
    def fail(*args,**kwargs):raise OSError("test-only simulated failure")
    monkeypatch.setattr(setup_owner,"save_owner_password",fail)
    root=tk.Tk();root.withdraw()
    dialog=setup_owner.OwnerPasswordDialog(root,tmp_path/".env")
    dialog.save()
    assert "Could not save" in dialog.status.get()
    assert not dialog.save_button.instate(["disabled"])
    dialog.cancel()
