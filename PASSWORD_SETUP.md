# Set your LokSutra owner password on Windows

## Easiest way
Double-click **Set Owner Password.cmd** in the LokSutra folder. It opens a local window with two masked fields: Password and Confirm password. Choose a new password or phrase of 12–256 characters. Enter the same value twice and click **Save owner password**.

A mismatch leaves the window open so you can retry. Cancel closes it without changing the configuration. The password is never printed, and only a salted scrypt hash is saved. This is your LokSutra login password, not your Gnani API key.

Then double-click **Start LokSutra.cmd** and open http://127.0.0.1:8000 in your browser. Sign in using the password you chose. Keep the server window open; Ctrl+C stops it. If you reset your password while the server is running, restart the server.

## Correct project folder
C:\Users\dell\Downloads\LokSutra_Hackathon_Project (2)\LokSutra

The launchers locate themselves, so they work even if CMD or PowerShell starts in another directory.

In CMD:
```bat
cd /d "C:\Users\dell\Downloads\LokSutra_Hackathon_Project (2)\LokSutra"
"Set Owner Password.cmd"
"Start LokSutra.cmd"
```

In VS Code's PowerShell terminal:
```powershell
Set-Location -LiteralPath 'C:\Users\dell\Downloads\LokSutra_Hackathon_Project (2)\LokSutra'
.\.venv\Scripts\python.exe setup_owner.py --gui
.\start_local.ps1
```

## Why the old terminal entry looked broken
The original script used Python getpass. It intentionally showed neither characters nor stars, so typing looked invisible. The confirmation compared both entries exactly: different capitalization, spaces or a missed character caused a mismatch. It then exited, forcing you to start over. This does not mean the keyboard was broken.

Windows now defaults to the graphical dialog. The explicit --cli option still offers hidden terminal input, explains that typing is invisible, and allows retries. Piped terminal password input is rejected.

## Safety and startup checks
- No built-in/default password. Only you choose the real one.
- Invalid/mismatched input changes nothing.
- The .env location is based on setup_owner.py, not your current terminal directory.
- Existing settings such as GNANI_API_KEY are preserved.
- Password hashing is shared with the backend; existing hashes remain compatible.
- The launcher checks the local Python environment and required imports, installs missing project dependencies if necessary, and requires a valid owner hash.
- Port 8000 conflicts produce a clear message; other processes are not stopped.
- .env and credentials are excluded from the source archive.
- Tcl/Tk is available on this machine. On another machine, use a desktop Python installation with Tcl/Tk support.
