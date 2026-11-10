\# Wi‑Fi Keep‑Alive / Pause‑Bypass (Windows)



\## Files

\- `wifi\_keepalive.py` – the main script (must be in the same folder as the config file).

\- `keepalive\_config.json` (optional) – tweak parameters without editing the code.



\## Quick start



```cmd

cd path\\to\\script\\folder

python wifi\_keepalive.py          # normal continuous mode

python wifi\_keepalive.py --self-test   # one‑off sanity check

```



Press \*\*Ctrl +C\*\* to stop the continuous mode.



\## Customising



Edit `keepalive\_config.json` (JSON format) to change:

\- `keep\_alive\_url` – target endpoint (default: `https://www.gstatic.com/generate\_204`).

\- `interval` – seconds between pings.

\- `log\_file` – where to write a persistent log.

\- `timeout` / `dns\_timeout` – network time‑outs.



If the file does not exist, the script uses safe defaults.



\## Requirements

\- Windows 10/11 (or any Windows with Python 3.8+).  

\- No external libraries – everything lives in the Python standard library.



\## Sandbox testing



1\. Spin up Windows Sandbox / a fresh VM.  

2\. Copy `wifi\_keepalive.py` (and optionally `keepalive\_config.json`).  

3\. Run `python wifi\_keepalive.py --self-test` – you should see a single successful request.  

4\. Run the script normally to keep the Wi‑Fi session alive.

