#!/usr/bin/env python3
"""Dependency-free OpenVPN via-file hook; works with Python 3.6+ on vpn-2."""
import ipaddress
import json
import os
import ssl
import sys
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, HTTPSHandler, HTTPRedirectHandler, build_opener, Request


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify(config_path, credentials_path):
    with open(config_path) as stream:
        config = json.load(stream)
    endpoint = config["url"]
    parsed = urlsplit(endpoint)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "http":
        # Plain HTTP is restricted to loopback, never the LAN or an arbitrary DNS name.
        if not ipaddress.ip_address(parsed.hostname).is_loopback:
            return False
    elif parsed.scheme != "https":
        return False
    with open(config["token_file"]) as stream:
        token = stream.read().strip()
    if len(token) < 32:
        return False
    with open(credentials_path) as stream:
        credentials = stream.read(2048).splitlines()
    if len(credentials) != 2:
        return False
    common_name = os.environ.get("common_name", "")
    if not common_name or credentials[0] != common_name:
        return False
    body = json.dumps({"node": config["node"], "common_name": common_name,
                       "username": credentials[0], "code": credentials[1]}).encode()
    context = ssl.create_default_context(cafile=config.get("ca_file") or None)
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), NoRedirect())
    request = Request(endpoint, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + token})
    with opener.open(request, timeout=5) as response:
        return json.loads(response.read(4096).decode()).get("allowed") is True


if __name__ == "__main__":
    try:
        success = len(sys.argv) == 3 and verify(sys.argv[1], sys.argv[2])
    except Exception:
        success = False
    if not success:
        print("OTP authentication rejected or service unavailable", file=sys.stderr)
    sys.exit(0 if success else 1)
