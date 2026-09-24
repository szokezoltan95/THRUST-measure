# Local THRUST WebDB alias

Run `install_host_alias.py` in an **administrator CMD** on Windows:

```cmd
py tools\install_host_alias.py
```

Or run it as root on Linux:

```sh
sudo python3 tools/install_host_alias.py
```

The script asks for the server IP and the local hostname, such as
`thrust-webdb.test`. It validates both inputs, updates the matching hostname
if one already exists, preserves other hosts entries, and creates a numbered
backup next to the original hosts file. Repeating it with the same values
does not change the file. It supports `--ip` and `--alias` for noninteractive
use. Use `--hosts-file /path/to/test-hosts` to preview on an ordinary test file.

Example: `147.232.204.163 thrust-webdb.test` makes the server reachable at
`http://thrust-webdb.test:8080` when WebDB listens on port 8080. A hosts entry
maps a hostname to an IP; it does not change the port. The WebDB server must
permit this hostname in its `ALLOWED_HOSTS` setting.
