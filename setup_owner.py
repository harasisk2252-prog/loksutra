"""Private local password setup. Windows defaults to a masked graphical dialog."""
import argparse
import os
import sys
from pathlib import Path
from dotenv import set_key
from owner_auth import password_hash

BASE = Path(__file__).resolve().parent

def save_owner_password(password, confirmation, target=None):
    """Validate before writing; target injection is only used by isolated tests."""
    if not 12 <= len(password) <= 256:
        raise ValueError("Use 12–256 characters. A memorable phrase works well.")
    if not password.strip():
        raise ValueError("The password cannot contain only spaces.")
    if password != confirmation:
        raise ValueError("The passwords do not match. Check Caps Lock and try again.")
    target = Path(target) if target is not None else BASE / ".env"
    # set_key preserves other settings and replaces the file atomically.
    set_key(str(target), "OWNER_PASSWORD_HASH", password_hash(password),
            quote_mode="always", encoding="utf-8-sig" if target.exists() and target.read_bytes().startswith(b"\xef\xbb\xbf") else "utf-8")
    if os.name != "nt":
        target.chmod(0o600)

class OwnerPasswordDialog:
    def __init__(self, root, target=None):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.target, self.saved = root, target, False
        self.password, self.confirmation = tk.StringVar(root), tk.StringVar(root)
        self.status = tk.StringVar(root, value="Both fields are hidden for privacy. Nothing is saved until you click Save.")
        root.title("LokSutra — Set owner password")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=24)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Set your LokSutra owner password", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,12))
        ttk.Label(frame, text="Choose a new phrase of at least 12 characters.\nThis is separate from your Gnani API key.", wraplength=470).grid(row=1,column=0,columnspan=2,sticky="w",pady=(0,16))
        ttk.Label(frame,text="Password").grid(row=2,column=0,columnspan=2,sticky="w")
        self.first = ttk.Entry(frame,textvariable=self.password,show="*",width=48)
        self.first.grid(row=3,column=0,columnspan=2,sticky="ew",pady=(4,12))
        ttk.Label(frame,text="Confirm password").grid(row=4,column=0,columnspan=2,sticky="w")
        self.second = ttk.Entry(frame,textvariable=self.confirmation,show="*",width=48)
        self.second.grid(row=5,column=0,columnspan=2,sticky="ew",pady=(4,12))
        ttk.Label(frame,textvariable=self.status,wraplength=470).grid(row=6,column=0,columnspan=2,sticky="w",pady=(0,12))
        ttk.Label(frame,text="Saves a salted hash in the .env beside setup_owner.py.\nYour password is never printed or stored as plain text.",wraplength=470).grid(row=7,column=0,columnspan=2,sticky="w",pady=(0,16))
        self.save_button = ttk.Button(frame,text="Save owner password",command=self.save)
        self.save_button.grid(row=8,column=0,sticky="w")
        ttk.Button(frame,text="Cancel",command=self.cancel).grid(row=8,column=1,sticky="e")
        self.first.bind("<Return>",lambda event:self.second.focus_set())
        self.second.bind("<Return>",lambda event:self.save())
        root.bind("<Escape>",lambda event:self.cancel())
        root.protocol("WM_DELETE_WINDOW",self.cancel)
        root.after(100,self.first.focus_set)

    def save(self):
        self.save_button.state(["disabled"])
        try:
            save_owner_password(self.password.get(),self.confirmation.get(),self.target)
        except ValueError as error:
            self.status.set(str(error))
            self.confirmation.set("")
            self.second.focus_set()
            self.save_button.state(["!disabled"])
            return
        except Exception:
            self.status.set("Could not save .env. Check that the project folder is writable, then try again.")
            self.save_button.state(["!disabled"])
            return
        self.saved = True
        self.password.set(""); self.confirmation.set("")
        from tkinter import messagebox
        messagebox.showinfo("LokSutra", "Owner password saved securely.\nStart or restart LokSutra, then use your password to sign in.", parent=self.root)
        self.root.destroy()

    def cancel(self):
        self.password.set(""); self.confirmation.set("")
        self.root.destroy()

def run_gui():
    import tkinter as tk
    root = tk.Tk()
    dialog = OwnerPasswordDialog(root)
    root.mainloop()
    return 0 if dialog.saved else 1

def run_cli():
    from getpass import getpass
    if not sys.stdin.isatty():
        print("Use the graphical setup in a local desktop session; piped password input is disabled.")
        return 1
    print("Password typing is intentionally invisible (no stars). Use --gui for visible masked fields.")
    while True:
        try:
            password = getpass("Choose owner password (12–256 characters): ")
            confirmation = getpass("Confirm owner password: ")
            save_owner_password(password, confirmation)
            print("Owner password saved securely. Restart LokSutra.")
            return 0
        except ValueError as error:
            print(str(error) + " Nothing changed; try again, or press Ctrl+C to cancel.")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled. Nothing changed.")
            return 1
        except OSError:
            print("Could not save .env. Check project-folder write access.")
            return 1
        finally:
            password = confirmation = None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui",action="store_true",help="Open two masked password fields")
    mode.add_argument("--cli",action="store_true",help="Use an interactive terminal instead")
    args = parser.parse_args()
    if args.gui or (os.name == "nt" and not args.cli):
        try:
            return run_gui()
        except Exception:
            print("The graphical dialog could not open. Use a desktop Python installation with Tk, or run setup_owner.py --cli in an interactive terminal.")
            return 1
    return run_cli()

if __name__ == "__main__":
    raise SystemExit(main())
