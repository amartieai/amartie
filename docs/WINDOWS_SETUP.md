# Windows setup

These steps use Windows 10/11, PowerShell or Command Prompt, and Python 3.9 or
newer. AMARTIE's cockpit is a local development server; it binds to
`127.0.0.1` on port `8715` and is not intended to be exposed to your network.

## 1. Install Python and clone

Install Python 3 from [python.org](https://www.python.org/downloads/windows/) or
the Microsoft Store. In a new terminal, check the Python launcher:

```powershell
py -3 --version
```

On Windows, `python` is commonly the command installed by python.org, while
`python3` is more common on macOS and Linux and may not be registered. `py -3`
selects an installed Python 3 version without relying on that alias. The steps
below use the `python` command after activating a virtual environment.

Clone the repository (Git must be installed and on `PATH`):

```powershell
git clone https://github.com/amartieai/amartie.git
cd amartie
```

## 2. Create and activate a virtual environment

In PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, either use the Command Prompt
activation below or allow scripts for this terminal process only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

In Command Prompt (`cmd.exe`):

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
```

The `(.venv)` prefix indicates that the environment is active. Install AMARTIE
and the test runner into it:

```console
python -m pip install --upgrade pip
python -m pip install -e . pytest
```

## 3. Run the tests

From the repository root, with the virtual environment active:

```console
python -m pytest tests -v
```

Using `python -m` ensures pip and pytest run under the same interpreter as the
active environment.

## 4. Start the local cockpit

In one terminal, from the repository root:

```console
python amartie\server.py 8715
```

Open <http://127.0.0.1:8715/visuals/cockpit.html> in your browser. Stop the
server with `Ctrl+C` when finished.

The server explicitly listens on the loopback address `127.0.0.1`, so it is
available only from this computer. If Windows Defender Firewall displays a
prompt, do not grant access on public networks; the local cockpit does not need
to be exposed to your LAN or the internet. If localhost does not load, check
that the server is still running and that another process is not already using
port `8715`.
