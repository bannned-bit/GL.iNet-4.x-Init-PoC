# GL.iNet 4.x init & empty-root-password PoC

Proof-of-concept for two unauthenticated attack paths against GL.iNet 4.x routers
(e.g. GL-BE10000) that have not completed first-time setup:

1. **SSH empty root password** — dropbear runs with `PasswordAuth` and
   `RootPasswordAuth` enabled, while `/etc/shadow` ships an *empty* root hash
   (`root::`) until `ui.init` sets one. Anyone on the LAN can log in as `root`
   with an empty password.
2. **`ui.init` takeover** — the web RPC endpoint `/rpc` exposes the
   `ui.check_initialized` / `ui.start_initialization` methods **without
   authentication** (`no-auth-methods` in `/etc/config/oui-httpd`). When
   `initialized == false`, an attacker can complete first-time setup and set
   their own admin + Wi-Fi passwords.

## Affected

- GL.iNet devices running firmware 4.x on a fresh unit or after factory reset
- Tested target: GL-BE10000 (Slate 7 Pro), firmware 4.8.4 release1
  (base: OpenWrt 21.02-SNAPSHOT, MediaTek MT7987)

## Requirements

- Python 3.8+
- `pip install -r requirements.txt`

## Usage

```
python3 gl_inet_poc.py <router_ip> [--port 22] [--cmd "id"] [--claim] [--no-web]
```

| Option     | Description                                               |
|------------|-----------------------------------------------------------|
| `--cmd`    | command to run via SSH after empty-password login         |
| `--claim`  | complete `ui.start_initialization` (CHANGES the device!)  |
| `--no-web` | skip the web `ui.init` check                              |

### Read-only check (safe)

```
python3 gl_inet_poc.py 192.168.8.1
```

### Run a command as root via empty-password SSH

```
python3 gl_inet_poc.py 192.168.8.1 --cmd "id; uname -a; cat /etc/glversion"
```

## How it works

1. **SSH path**: attempts `root` with `password=""` via paramiko. On success,
   executes the requested command.
2. **Web path**: calls the unauthenticated RPC `ui.check_initialized`. If
   `initialized == false`, the unit is claimable. With `--claim`, calls
   `ui.start_initialization` with attacker-chosen admin/Wi-Fi passwords.

## Impact

- Unauthenticated (pre-setup) LAN attacker gains **root** on the router:
  DNS, traffic interception, persistence, LAN pivot.
- Root access also exposes old components (e.g. dnsmasq 2.85 in the tested
  firmware), widening the attack surface.

## Mitigation / Fix

- Complete the setup wizard on first boot (sets a strong root password).
- Or run `passwd root` manually, then restrict SSH:
  - `uci set dropbear.@dropbear[0].PasswordAuth='0'`
  - `uci set dropbear.@dropbear[0].RootPasswordAuth='0'`
  - `uci commit dropbear && /etc/init.d/dropbear restart`
- Keep firmware updated (GL.iNet 4.x advisories: CVE-2024-57391, CVE-2025-2811,
  CVE-2025-2850, CVE-2025-2851).

## References

- GL.iNet security advisories: https://www.gl-inet.com/security-advisories/
- CVE-2024-57391, CVE-2025-2811, CVE-2025-2850, CVE-2025-2851

## Disclaimer

For authorized security research and testing on devices you own or have
permission to test only. `--claim` permanently changes the target device.
