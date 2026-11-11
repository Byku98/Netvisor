"""Device classifier — identifies device types using MAC OUI + packet header analysis.

Each IP is classified ONCE and cached. Uses probability scoring to combine
MAC manufacturer info with observed packet behavior.

Classification pipeline:
    1. MAC OUI lookup → base manufacturer type (high confidence)
    2. Packet header analysis → validate/refine type
    3. Cache result per IP — never re-classify
"""

from collections import Counter
from dataclasses import dataclass, field

from src.logging import get_logger
from src.services.parser import RawPacket

log = get_logger("classifier")


# ── OUI Database ───────────────────────────────────────────────────────
# Maps first 3 bytes of MAC (manufacturer) to device type.
# Only common manufacturers — covers ~95% of real-world networks.

_OUI_PREFIXES: dict[str, str] = {
    # ── Network Equipment (routers/switches) ──
    "00:00:0c": "router",       # Cisco
    "00:01:42": "router",       # Cisco
    "00:01:43": "router",       # Cisco
    "00:01:63": "switch",       # Cisco (switches)
    "00:01:64": "switch",       # Cisco (switches)
    "00:01:96": "switch",       # Cisco (switches)
    "00:01:97": "switch",       # Cisco (switches)
    "00:01:c7": "router",       # Cisco
    "00:01:c9": "router",       # Cisco
    "00:0a:41": "router",       # Cisco
    "00:0b:be": "router",       # Cisco
    "00:0d:bc": "router",       # Cisco
    "00:0e:38": "router",       # Cisco
    "00:0e:d7": "router",       # Cisco
    "00:11:21": "router",       # Cisco
    "00:11:5c": "router",       # Cisco
    "00:12:43": "router",       # Cisco
    "00:13:19": "router",       # Cisco
    "00:13:7f": "router",       # Cisco
    "00:14:6a": "router",       # Cisco
    "00:16:46": "switch",       # Cisco (switches)
    "00:17:0e": "switch",       # Cisco (switches)
    "00:17:94": "switch",       # Cisco (switches)
    "00:18:73": "switch",       # Cisco (switches)
    "00:19:2f": "switch",       # Cisco (switches)
    "00:19:aa": "switch",       # Cisco (switches)
    "00:1a:a1": "switch",       # Cisco (switches)
    "00:1b:0c": "switch",       # Cisco (switches)
    "00:1b:53": "switch",       # Cisco (switches)
    "00:1b:54": "switch",       # Cisco (switches)
    "00:1c:0e": "switch",       # Cisco (switches)
    "00:1c:0f": "switch",       # Cisco (switches)
    "00:1e:13": "switch",       # Cisco (switches)
    "00:1e:49": "switch",       # Cisco (switches)
    "00:1e:be": "switch",       # Cisco (switches)
    "00:21:55": "switch",       # Cisco (switches)
    "00:22:55": "switch",       # Cisco (switches)
    "00:23:33": "switch",       # Cisco (switches)
    "00:24:13": "switch",       # Cisco (switches)
    "00:25:45": "switch",       # Cisco (switches)
    "00:26:51": "switch",       # Cisco (switches)
    "00:27:0c": "switch",       # Cisco (switches)
    "04:c5:a4": "router",       # Cisco
    "08:cc:68": "router",       # Cisco
    "0c:85:25": "router",       # Cisco
    "10:fa:ce": "router",       # Cisco
    "18:8b:9e": "router",       # Cisco
    "1c:aa:07": "router",       # Cisco
    "20:bb:bc": "router",       # Cisco
    "24:01:c7": "router",       # Cisco
    "28:94:0f": "router",       # Cisco
    "30:f7:0d": "router",       # Cisco
    "3c:ce:73": "router",       # Cisco
    "40:55:39": "router",       # Cisco
    "44:03:a7": "router",       # Cisco
    "48:44:87": "router",       # Cisco
    "4c:4e:35": "router",       # Cisco
    "50:06:04": "router",       # Cisco
    "54:78:1a": "router",       # Cisco
    "58:97:1e": "router",       # Cisco
    "5c:50:15": "router",       # Cisco
    "5c:83:8f": "router",       # Cisco
    "64:f6:9d": "router",       # Cisco
    "68:86:a7": "router",       # Cisco
    "6c:20:56": "router",       # Cisco
    "70:db:98": "router",       # Cisco
    "74:a0:2f": "router",       # Cisco
    "78:ba:f9": "router",       # Cisco
    "7c:0e:ce": "router",       # Cisco
    "84:78:ac": "router",       # Cisco
    "88:5a:92": "router",       # Cisco
    "8c:60:4f": "router",       # Cisco
    "94:d4:69": "router",       # Cisco
    "98:fc:11": "router",       # Cisco
    "a0:3d:6f": "router",       # Cisco
    "a0:ec:f9": "router",       # Cisco
    "a4:56:30": "router",       # Cisco
    "a8:0c:0d": "router",       # Cisco
    "ac:4e:91": "router",       # Cisco
    "b0:aa:77": "router",       # Cisco
    "b4:a4:e3": "router",       # Cisco
    "b8:38:61": "router",       # Cisco
    "c4:64:13": "router",       # Cisco
    "c8:00:84": "router",       # Cisco
    "cc:16:7e": "router",       # Cisco
    "d0:72:dc": "router",       # Cisco
    "d4:d7:48": "router",       # Cisco
    "dc:eb:94": "router",       # Cisco
    "ec:44:76": "router",       # Cisco
    "f0:29:29": "router",       # Cisco
    "f4:4e:05": "router",       # Cisco
    "fc:5b:39": "router",       # Cisco

    # Juniper
    "00:05:85": "router",       # Juniper
    "00:10:db": "router",       # Juniper
    "00:12:1e": "router",       # Juniper
    "00:17:cb": "router",       # Juniper
    "00:19:e2": "router",       # Juniper
    "00:1f:12": "router",       # Juniper
    "00:21:59": "router",       # Juniper
    "00:22:83": "router",       # Juniper
    "00:23:9c": "router",       # Juniper
    "00:24:dc": "router",       # Juniper
    "00:26:88": "router",       # Juniper
    "00:db:12": "router",       # Juniper
    "28:8a:1c": "router",       # Juniper
    "2c:6b:f5": "router",       # Juniper
    "3c:61:04": "router",       # Juniper
    "40:a6:77": "router",       # Juniper
    "54:1e:56": "router",       # Juniper
    "5c:45:27": "router",       # Juniper
    "64:87:88": "router",       # Juniper
    "78:fe:3d": "router",       # Juniper
    "80:71:1f": "router",       # Juniper
    "84:18:88": "router",       # Juniper
    "84:b5:9c": "router",       # Juniper
    "88:e0:f3": "router",       # Juniper
    "9c:cc:83": "router",       # Juniper
    "a8:d0:e5": "router",       # Juniper
    "b0:c6:9a": "router",       # Juniper
    "b0:e2:e5": "router",       # Juniper
    "c8:fe:30": "router",       # Juniper
    "d4:04:ff": "router",       # Juniper
    "ec:13:db": "router",       # Juniper
    "ec:3e:f7": "router",       # Juniper
    "f0:1c:2d": "router",       # Juniper
    "f4:a7:39": "router",       # Juniper
    "f4:b5:2f": "router",       # Juniper
    "f8:c0:01": "router",       # Juniper

    # MikroTik
    "00:0c:42": "router",       # MikroTik
    "48:8f:5a": "router",       # MikroTik
    "74:4d:28": "router",       # MikroTik
    "b8:69:f4": "router",       # MikroTik
    "cc:2d:e0": "router",       # MikroTik
    "d4:01:c3": "router",       # MikroTik

    # TP-Link
    "54:c8:0f": "router",       # TP-Link
    "60:32:b1": "router",       # TP-Link
    "98:da:c4": "router",       # TP-Link
    "b0:4e:26": "router",       # TP-Link
    "c0:06:c3": "router",       # TP-Link
    "e8:de:27": "router",       # TP-Link

    # Ubiquiti
    "04:18:d6": "router",       # Ubiquiti
    "24:5a:4c": "router",       # Ubiquiti
    "44:d9:e7": "router",       # Ubiquiti
    "68:72:51": "router",       # Ubiquiti
    "74:ac:b9": "router",       # Ubiquiti
    "78:8a:20": "router",       # Ubiquiti
    "80:2a:a8": "router",       # Ubiquiti
    "b2:fb:af": "router",       # Ubiquiti
    "d8:13:2a": "router",       # Ubiquiti
    "e0:63:da": "router",       # Ubiquiti
    "f0:9f:c2": "router",       # Ubiquiti
    "fc:ec:da": "router",       # Ubiquiti

    # ── Firewalls ──
    "08:95:2a": "firewall",     # Palo Alto Networks
    "00:1b:17": "firewall",     # Palo Alto Networks
    "00:e0:4c": "firewall",     # Realtek (common in pfSense boxes)
    "00:0d:b9": "firewall",     # PC Engines (pfSense/OPNsense hardware)
    "00:0d:b4": "firewall",     # Fortinet
    "00:09:0f": "firewall",     # Fortinet
    "00:1a:2b": "firewall",     # Fortinet
    "00:26:fa": "firewall",     # Fortinet
    "00:60:73": "firewall",     # Fortinet
    "00:90:fb": "firewall",     # Fortinet
    "04:d5:90": "firewall",     # Fortinet
    "08:4e:1a": "firewall",     # Fortinet
    "0c:a8:a7": "firewall",     # Fortinet
    "10:28:3c": "firewall",     # Fortinet
    "18:0b:52": "firewall",     # Fortinet
    "1c:96:5a": "firewall",     # Fortinet
    "20:4c:9e": "firewall",     # Fortinet
    "24:69:68": "firewall",     # Fortinet
    "28:48:46": "firewall",     # Fortinet
    "2c:41:38": "firewall",     # Fortinet
    "30:5a:3a": "firewall",     # Fortinet
    "34:64:a9": "firewall",     # Fortinet
    "38:4c:fb": "firewall",     # Fortinet
    "3c:1e:04": "firewall",     # Fortinet
    "40:62:31": "firewall",     # Fortinet
    "44:38:39": "firewall",     # Fortinet
    "48:87:2d": "firewall",     # Fortinet
    "4c:96:14": "firewall",     # Fortinet
    "50:09:e5": "firewall",     # Fortinet
    "54:27:8d": "firewall",     # Fortinet
    "58:50:ab": "firewall",     # Fortinet
    "5c:86:4a": "firewall",     # Fortinet
    "60:2a:d0": "firewall",     # Fortinet
    "64:7c:34": "firewall",     # Fortinet
    "68:1a:b2": "firewall",     # Fortinet
    "6c:3b:6b": "firewall",     # Fortinet
    "70:4c:a5": "firewall",     # Fortinet
    "74:99:75": "firewall",     # Fortinet
    "78:ac:44": "firewall",     # Fortinet
    "80:66:29": "firewall",     # Fortinet
    "88:09:af": "firewall",     # Fortinet
    "90:c7:92": "firewall",     # Fortinet
    "94:2c:af": "firewall",     # Fortinet
    "98:4f:ee": "firewall",     # Fortinet
    "9c:1c:12": "firewall",     # Fortinet
    "a4:c2:ab": "firewall",     # Fortinet
    "ac:16:2d": "firewall",     # Fortinet
    "b0:41:6f": "firewall",     # Fortinet
    "b4:0e:cf": "firewall",     # Fortinet
    "b8:81:98": "firewall",     # Fortinet
    "bc:0f:9a": "firewall",     # Fortinet
    "c0:7c:01": "firewall",     # Fortinet
    "c4:12:34": "firewall",     # Fortinet
    "c8:63:f1": "firewall",     # Fortinet
    "cc:21:19": "firewall",     # Fortinet
    "d0:05:9a": "firewall",     # Fortinet
    "d4:76:ea": "firewall",     # Fortinet
    "dc:f3:1c": "firewall",     # Fortinet
    "e0:23:ff": "firewall",     # Fortinet
    "e4:75:dc": "firewall",     # Fortinet
    "e8:1c:ba": "firewall",     # Fortinet
    "f0:43:47": "firewall",     # Fortinet
    "f4:5f:d4": "firewall",     # Fortinet
    "f8:22:29": "firewall",     # Fortinet

    # Checkpoint
    "00:1c:7f": "firewall",     # Checkpoint
    "00:03:b2": "firewall",     # Checkpoint

    # SonicWall
    "00:17:c5": "firewall",     # SonicWall
    "00:06:b1": "firewall",     # SonicWall

    # pfSense (Netgate)
    "00:08:a2": "firewall",     # Netgate

    # ── Servers / Enterprise ──
    "00:0c:29": "server",       # VMware
    "00:50:56": "server",       # VMware
    "00:0f:4b": "server",       # Oracle/Sun
    "00:14:4f": "server",       # Oracle/Sun
    "00:21:28": "server",       # Oracle/Sun
    "00:03:ba": "server",       # HP/Compaq
    "00:08:02": "server",       # HP
    "00:0d:9d": "server",       # HP
    "00:0e:7f": "server",       # HP
    "00:0f:20": "server",       # HP
    "00:10:83": "server",       # HP
    "00:11:0a": "server",       # HP
    "00:11:85": "server",       # HP
    "00:12:79": "server",       # HP
    "00:13:21": "server",       # HP
    "00:14:38": "server",       # HP
    "00:15:60": "server",       # HP
    "00:16:35": "server",       # HP
    "00:17:a4": "server",       # HP
    "00:18:fe": "server",       # HP
    "00:1a:4b": "server",       # HP
    "00:1b:78": "server",       # HP
    "00:1c:c4": "server",       # HP
    "00:1e:0b": "server",       # HP
    "00:21:5a": "server",       # HP
    "00:23:7d": "server",       # HP
    "00:25:b3": "server",       # HP
    "00:1e:67": "server",       # Dell
    "00:14:22": "server",       # Dell
    "00:15:c5": "server",       # Dell
    "00:18:8b": "server",       # Dell
    "00:19:b9": "server",       # Dell
    "00:1a:a0": "server",       # Dell
    "00:1c:23": "server",       # Dell
    "00:21:9b": "server",       # Dell
    "00:22:19": "server",       # Dell
    "00:24:e8": "server",       # Dell
    "00:26:b9": "server",       # Dell
    "14:18:77": "server",       # Dell
    "18:a9:9b": "server",       # Dell
    "34:17:eb": "server",       # Dell
    "78:2b:cb": "server",       # Dell
    "b0:83:fe": "server",       # Dell
    "b8:2a:72": "server",       # Dell
    "d4:ae:52": "server",       # Dell
    "f0:1f:af": "server",       # Dell
    "f8:b1:56": "server",       # Dell
    "f8:bc:12": "server",       # Dell
    "f8:db:88": "server",       # Dell
    "44:a8:42": "server",       # Dell
    "00:1a:64": "server",       # Lenovo
    "00:0e:0c": "server",       # Lenovo
    "00:21:5e": "server",       # Lenovo
    "00:23:76": "server",       # Lenovo
    "00:25:b5": "server",       # Lenovo
    "3c:97:0e": "server",       # Lenovo
    "60:eb:69": "server",       # Lenovo
    "78:2b:46": "server",       # Lenovo
    "8c:ec:4b": "server",       # Lenovo
    "cc:3d:82": "server",       # Lenovo
    "d8:9e:f3": "server",       # Lenovo
    "f0:de:f1": "server",       # Lenovo
    "f8:a9:d0": "server",       # Lenovo
    "00:25:90": "server",       # Supermicro
    "0c:c4:7a": "server",       # Supermicro
    "ac:1f:6b": "server",       # Supermicro

    # ── Cloud / Hosting ──
    "02:42:ac": "server",       # Docker containers
    "02:42:0a": "server",       # Docker containers

    # ── Consumer / Clients ──
    "00:03:93": "client",       # Apple
    "00:0a:95": "client",       # Apple
    "00:0d:93": "client",       # Apple
    "00:11:24": "client",       # Apple
    "00:14:51": "client",       # Apple
    "00:16:cb": "client",       # Apple
    "00:17:f2": "client",       # Apple
    "00:19:e3": "client",       # Apple
    "00:1b:63": "client",       # Apple
    "00:1e:c2": "client",       # Apple
    "00:21:e9": "client",       # Apple
    "00:22:41": "client",       # Apple
    "00:23:12": "client",       # Apple
    "00:23:32": "client",       # Apple
    "00:23:df": "client",       # Apple
    "00:24:36": "client",       # Apple
    "00:25:00": "client",       # Apple
    "00:25:4b": "client",       # Apple
    "00:26:08": "client",       # Apple
    "00:26:4a": "client",       # Apple
    "00:26:b0": "client",       # Apple
    "00:26:bb": "client",       # Apple
    "04:0c:ce": "client",       # Apple
    "04:15:52": "client",       # Apple
    "04:1e:64": "client",       # Apple
    "04:26:65": "client",       # Apple
    "04:48:82": "client",       # Apple
    "04:54:53": "client",       # Apple
    "04:69:f8": "client",       # Apple
    "04:d3:cf": "client",       # Apple
    "04:db:56": "client",       # Apple
    "04:f1:3e": "client",       # Apple
    "08:6d:41": "client",       # Apple
    "08:74:02": "client",       # Apple
    "0c:4d:e9": "client",       # Apple
    "0c:74:c2": "client",       # Apple
    "10:1c:0c": "client",       # Apple
    "10:40:f3": "client",       # Apple
    "10:93:e9": "client",       # Apple
    "10:dd:b1": "client",       # Apple
    "14:10:9f": "client",       # Apple
    "14:20:5e": "client",       # Apple
    "14:7d:da": "client",       # Apple
    "14:8f:c6": "client",       # Apple
    "14:99:e2": "client",       # Apple
    "14:bd:61": "client",       # Apple
    "18:34:51": "client",       # Apple
    "18:af:61": "client",       # Apple
    "18:e7:f4": "client",       # Apple
    "1c:ab:a7": "client",       # Apple
    "1c:e6:2b": "client",       # Apple
    "20:78:f0": "client",       # Apple
    "20:a2:e4": "client",       # Apple
    "20:c9:d0": "client",       # Apple
    "24:1e:eb": "client",       # Apple
    "24:a0:74": "client",       # Apple
    "24:f0:94": "client",       # Apple
    "28:cf:e9": "client",       # Apple
    "28:e0:2c": "client",       # Apple
    "2c:1f:23": "client",       # Apple
    "2c:b4:3a": "client",       # Apple
    "30:10:e4": "client",       # Apple
    "30:35:ad": "client",       # Apple
    "30:f7:c5": "client",       # Apple
    "34:15:9e": "client",       # Apple
    "34:36:3b": "client",       # Apple
    "34:51:c9": "client",       # Apple
    "34:a3:95": "client",       # Apple
    "34:ab:37": "client",       # Apple
    "34:c0:59": "client",       # Apple
    "34:e2:fd": "client",       # Apple
    "38:0f:4a": "client",       # Apple
    "38:48:4c": "client",       # Apple
    "38:71:de": "client",       # Apple
    "3c:15:c2": "client",       # Apple
    "3c:22:fb": "client",       # Apple
    "3c:e0:72": "client",       # Apple
    "40:30:04": "client",       # Apple
    "40:33:1a": "client",       # Apple
    "40:6c:8f": "client",       # Apple
    "40:a6:d9": "client",       # Apple
    "40:b3:95": "client",       # Apple
    "40:d3:2d": "client",       # Apple
    "44:00:10": "client",       # Apple
    "44:4c:0c": "client",       # Apple
    "44:65:0d": "client",       # Apple
    "44:d1:fa": "client",       # Apple
    "44:fb:42": "client",       # Apple
    "48:3b:38": "client",       # Apple
    "48:43:dd": "client",       # Apple
    "48:60:bc": "client",       # Apple
    "48:74:6e": "client",       # Apple
    "48:d7:05": "client",       # Apple
    "48:e9:f1": "client",       # Apple
    "4c:32:75": "client",       # Apple
    "4c:57:ca": "client",       # Apple
    "4c:7c:5f": "client",       # Apple
    "4c:8d:79": "client",       # Apple
    "4c:b1:9c": "client",       # Apple
    "50:32:37": "client",       # Apple
    "50:46:5d": "client",       # Apple
    "50:7a:55": "client",       # Apple
    "50:ea:d6": "client",       # Apple
    "54:26:96": "client",       # Apple
    "54:4e:90": "client",       # Apple
    "54:72:4f": "client",       # Apple
    "54:ae:27": "client",       # Apple
    "54:e4:3a": "client",       # Apple
    "58:1f:aa": "client",       # Apple
    "58:40:4e": "client",       # Apple
    "58:55:ca": "client",       # Apple
    "58:7f:57": "client",       # Apple
    "58:b0:35": "client",       # Apple
    "58:d5:6e": "client",       # Apple
    "58:e6:ba": "client",       # Apple
    "58:fb:84": "client",       # Apple
    "5c:59:48": "client",       # Apple
    "5c:8d:4e": "client",       # Apple
    "5c:95:ae": "client",       # Apple
    "5c:96:9d": "client",       # Apple
    "5c:f7:e6": "client",       # Apple
    "5c:f9:38": "client",       # Apple
    "60:03:08": "client",       # Apple
    "60:33:4b": "client",       # Apple
    "60:69:44": "client",       # Apple
    "60:92:17": "client",       # Apple
    "60:ab:d2": "client",       # Apple
    "60:c5:47": "client",       # Apple
    "60:d9:c7": "client",       # Apple
    "60:f4:45": "client",       # Apple
    "60:f8:1d": "client",       # Apple
    "60:fa:cd": "client",       # Apple
    "60:fb:42": "client",       # Apple
    "64:20:0c": "client",       # Apple
    "64:4b:f0": "client",       # Apple
    "64:5a:ed": "client",       # Apple
    "64:76:ba": "client",       # Apple
    "64:89:9a": "client",       # Apple
    "64:a3:cb": "client",       # Apple
    "64:b9:e8": "client",       # Apple
    "64:db:81": "client",       # Apple
    "64:e6:82": "client",       # Apple
    "68:09:27": "client",       # Apple
    "68:5b:35": "client",       # Apple
    "68:64:4b": "client",       # Apple
    "68:96:7b": "client",       # Apple
    "68:9c:70": "client",       # Apple
    "68:a8:6d": "client",       # Apple
    "68:ab:1e": "client",       # Apple
    "68:d9:3c": "client",       # Apple
    "68:db:ca": "client",       # Apple
    "68:fb:7e": "client",       # Apple
    "6c:19:c0": "client",       # Apple
    "6c:3e:6d": "client",       # Apple
    "6c:40:08": "client",       # Apple
    "6c:70:9f": "client",       # Apple
    "6c:72:e7": "client",       # Apple
    "6c:8d:c1": "client",       # Apple
    "6c:96:cf": "client",       # Apple
    "6c:ab:31": "client",       # Apple
    "6c:d1:b0": "client",       # Apple
    "70:11:24": "client",       # Apple
    "70:14:a6": "client",       # Apple
    "70:48:0f": "client",       # Apple
    "70:56:81": "client",       # Apple
    "70:cd:60": "client",       # Apple
    "70:de:e2": "client",       # Apple
    "70:ec:e4": "client",       # Apple
    "70:f0:87": "client",       # Apple
    "74:40:be": "client",       # Apple
    "74:81:14": "client",       # Apple
    "74:e1:b6": "client",       # Apple
    "74:e2:f5": "client",       # Apple
    "78:31:c1": "client",       # Apple
    "78:3a:84": "client",       # Apple
    "78:6c:1c": "client",       # Apple
    "78:7b:8a": "client",       # Apple
    "78:7e:61": "client",       # Apple
    "78:88:6d": "client",       # Apple
    "78:a3:e4": "client",       # Apple
    "78:ca:39": "client",       # Apple
    "78:d7:5f": "client",       # Apple
    "78:fd:b4": "client",       # Apple
    "78:ff:ca": "client",       # Apple
    "7c:01:91": "client",       # Apple
    "7c:11:be": "client",       # Apple
    "7c:50:49": "client",       # Apple
    "7c:6d:62": "client",       # Apple
    "7c:6d:f8": "client",       # Apple
    "7c:79:4b": "client",       # Apple
    "7c:b0:c2": "client",       # Apple
    "7c:d1:c3": "client",       # Apple
    "7c:f0:5f": "client",       # Apple
    "7c:fa:df": "client",       # Apple
    "80:49:71": "client",       # Apple
    "80:92:9f": "client",       # Apple
    "80:b0:3d": "client",       # Apple
    "80:be:05": "client",       # Apple
    "80:d6:05": "client",       # Apple
    "80:e6:50": "client",       # Apple
    "80:ed:2c": "client",       # Apple
    "84:29:99": "client",       # Apple
    "84:38:35": "client",       # Apple
    "84:41:67": "client",       # Apple
    "84:85:06": "client",       # Apple
    "84:89:ad": "client",       # Apple
    "84:fc:ac": "client",       # Apple
    "84:fe:9e": "client",       # Apple
    "88:19:08": "client",       # Apple
    "88:1f:a1": "client",       # Apple
    "88:63:df": "client",       # Apple
    "88:66:a5": "client",       # Apple
    "88:ae:07": "client",       # Apple
    "88:c3:97": "client",       # Apple
    "88:cb:87": "client",       # Apple
    "88:e8:7f": "client",       # Apple
    "88:f0:77": "client",       # Apple
    "8c:00:6d": "client",       # Apple
    "8c:29:37": "client",       # Apple
    "8c:2a:8e": "client",       # Apple
    "8c:2d:aa": "client",       # Apple
    "8c:58:77": "client",       # Apple
    "8c:7c:92": "client",       # Apple
    "8c:85:90": "client",       # Apple
    "8c:8e:f2": "client",       # Apple
    "8c:8f:e9": "client",       # Apple
    "8c:fa:ba": "client",       # Apple
    "8c:fe:b8": "client",       # Apple
    "90:27:e4": "client",       # Apple
    "90:3c:92": "client",       # Apple
    "90:72:40": "client",       # Apple
    "90:81:58": "client",       # Apple
    "90:84:0d": "client",       # Apple
    "90:8d:6c": "client",       # Apple
    "90:b0:ed": "client",       # Apple
    "90:b2:1f": "client",       # Apple
    "90:c1:c6": "client",       # Apple
    "90:dd:5d": "client",       # Apple
    "90:fd:61": "client",       # Apple
    "94:94:26": "client",       # Apple
    "94:e9:79": "client",       # Apple
    "94:f6:a3": "client",       # Apple
    "98:01:a7": "client",       # Apple
    "98:5a:eb": "client",       # Apple
    "98:d6:bb": "client",       # Apple
    "98:e0:d9": "client",       # Apple
    "98:f0:ab": "client",       # Apple
    "98:fe:94": "client",       # Apple
    "9c:20:7b": "client",       # Apple
    "9c:35:eb": "client",       # Apple
    "9c:7b:ef": "client",       # Apple
    "9c:84:bf": "client",       # Apple
    "9c:b2:b2": "client",       # Apple
    "9c:f3:87": "client",       # Apple
    "9c:f4:8e": "client",       # Apple
    "a0:18:28": "client",       # Apple
    "a0:3b:e3": "client",       # Apple
    "a0:99:9b": "client",       # Apple
    "a0:ed:cd": "client",       # Apple
    "a4:31:35": "client",       # Apple
    "a4:5e:60": "client",       # Apple
    "a4:67:06": "client",       # Apple
    "a4:83:e7": "client",       # Apple
    "a4:b1:97": "client",       # Apple
    "a4:b8:05": "client",       # Apple
    "a4:d1:8c": "client",       # Apple
    "a4:d1:d2": "client",       # Apple
    "a8:16:b2": "client",       # Apple
    "a8:20:66": "client",       # Apple
    "a8:5c:2c": "client",       # Apple
    "a8:66:7f": "client",       # Apple
    "a8:86:dd": "client",       # Apple
    "a8:88:08": "client",       # Apple
    "a8:be:27": "client",       # Apple
    "a8:fa:d8": "client",       # Apple
    "ac:1f:74": "client",       # Apple
    "ac:29:3a": "client",       # Apple
    "ac:3c:0b": "client",       # Apple
    "ac:61:ea": "client",       # Apple
    "ac:7f:3e": "client",       # Apple
    "ac:87:a3": "client",       # Apple
    "ac:bc:32": "client",       # Apple
    "ac:cf:5c": "client",       # Apple
    "ac:d1:b8": "client",       # Apple
    "ac:e4:b5": "client",       # Apple
    "ac:fd:ec": "client",       # Apple
    "b0:00:b4": "client",       # Apple
    "b0:34:95": "client",       # Apple
    "b0:48:7a": "client",       # Apple
    "b0:ca:68": "client",       # Apple
    "b4:18:d1": "client",       # Apple
    "b4:4b:d2": "client",       # Apple
    "b4:8b:19": "client",       # Apple
    "b4:9c:df": "client",       # Apple
    "b4:f0:ab": "client",       # Apple
    "b4:f6:1c": "client",       # Apple
    "b8:09:f5": "client",       # Apple
    "b8:17:c2": "client",       # Apple
    "b8:41:a4": "client",       # Apple
    "b8:44:d9": "client",       # Apple
    "b8:5d:0a": "client",       # Apple
    "b8:63:4d": "client",       # Apple
    "b8:78:2e": "client",       # Apple
    "b8:8d:12": "client",       # Apple
    "b8:e8:56": "client",       # Apple
    "b8:f0:09": "client",       # Apple
    "b8:f6:b1": "client",       # Apple
    "b8:ff:61": "client",       # Apple
    "bc:3b:af": "client",       # Apple
    "bc:52:b7": "client",       # Apple
    "bc:67:78": "client",       # Apple
    "bc:6c:21": "client",       # Apple
    "bc:9f:ef": "client",       # Apple
    "bc:ec:5d": "client",       # Apple
    "c0:1a:da": "client",       # Apple
    "c0:63:94": "client",       # Apple
    "c0:84:7d": "client",       # Apple
    "c0:8a:de": "client",       # Apple
    "c0:9a:d0": "client",       # Apple
    "c0:b6:58": "client",       # Apple
    "c0:d0:12": "client",       # Apple
    "c0:f2:fb": "client",       # Apple
    "c4:14:3c": "client",       # Apple
    "c4:2c:03": "client",       # Apple
    "c4:3a:be": "client",       # Apple
    "c4:61:8b": "client",       # Apple
    "c4:b3:01": "client",       # Apple
    "c4:f5:7c": "client",       # Apple
    "c8:1e:e7": "client",       # Apple
    "c8:2a:14": "client",       # Apple
    "c8:33:4b": "client",       # Apple
    "c8:3c:85": "client",       # Apple
    "c8:69:cd": "client",       # Apple
    "c8:6f:1d": "client",       # Apple
    "c8:b1:ee": "client",       # Apple
    "c8:b3:73": "client",       # Apple
    "c8:bc:c8": "client",       # Apple
    "c8:d0:83": "client",       # Apple
    "c8:f6:50": "client",       # Apple
    "cc:08:8d": "client",       # Apple
    "cc:25:00": "client",       # Apple
    "cc:29:f5": "client",       # Apple
    "cc:44:63": "client",       # Apple
    "cc:46:d6": "client",       # Apple
    "cc:78:5f": "client",       # Apple
    "cc:c7:60": "client",       # Apple
    "d0:03:4b": "client",       # Apple
    "d0:23:db": "client",       # Apple
    "d0:33:11": "client",       # Apple
    "d0:4f:7e": "client",       # Apple
    "d0:81:7a": "client",       # Apple
    "d0:a6:37": "client",       # Apple
    "d0:c5:f3": "client",       # Apple
    "d0:d2:b0": "client",       # Apple
    "d0:e1:40": "client",       # Apple
    "d4:61:9d": "client",       # Apple
    "d4:61:da": "client",       # Apple
    "d4:9a:20": "client",       # Apple
    "d4:a3:3d": "client",       # Apple
    "d6:1b:52": "client",       # Apple (local admin)
    "d8:00:4d": "client",       # Apple
    "d8:1c:79": "client",       # Apple
    "d8:8f:76": "client",       # Apple
    "d8:96:95": "client",       # Apple
    "d8:9e:3f": "client",       # Apple
    "d8:a2:5e": "client",       # Apple
    "d8:bb:c1": "client",       # Apple
    "d8:d1:cb": "client",       # Apple
    "dc:2b:2a": "client",       # Apple
    "dc:2b:61": "client",       # Apple
    "dc:37:45": "client",       # Apple
    "dc:38:e1": "client",       # Apple
    "dc:41:5f": "client",       # Apple
    "dc:56:e7": "client",       # Apple
    "dc:65:cf": "client",       # Apple
    "dc:86:d8": "client",       # Apple
    "dc:9b:9c": "client",       # Apple
    "dc:a4:ca": "client",       # Apple
    "dc:a9:04": "client",       # Apple
    "dc:f5:1b": "client",       # Apple
    "e0:66:78": "client",       # Apple
    "e0:ac:cb": "client",       # Apple
    "e0:b5:5f": "client",       # Apple
    "e0:b9:ba": "client",       # Apple
    "e0:c7:67": "client",       # Apple
    "e0:c9:7a": "client",       # Apple
    "e4:25:e7": "client",       # Apple
    "e4:2b:34": "client",       # Apple
    "e4:8b:7f": "client",       # Apple
    "e4:9a:dc": "client",       # Apple
    "e4:c6:37": "client",       # Apple
    "e4:d3:32": "client",       # Apple
    "e4:ea:83": "client",       # Apple
    "e8:09:45": "client",       # Apple
    "e8:36:17": "client",       # Apple
    "e8:42:f3": "client",       # Apple
    "e8:48:b8": "client",       # Apple
    "e8:51:6d": "client",       # Apple
    "e8:7f:95": "client",       # Apple
    "e8:80:2e": "client",       # Apple
    "e8:b2:ac": "client",       # Apple
    "e8:c0:dd": "client",       # Apple
    "e8:db:84": "client",       # Apple
    "ec:28:d3": "client",       # Apple
    "ec:35:86": "client",       # Apple
    "ec:5c:68": "client",       # Apple
    "ec:85:2f": "client",       # Apple
    "ec:b1:d7": "client",       # Apple
    "ec:fa:bc": "client",       # Apple
    "f0:18:98": "client",       # Apple
    "f0:24:75": "client",       # Apple
    "f0:6e:0b": "client",       # Apple
    "f0:71:7c": "client",       # Apple
    "f0:72:ea": "client",       # Apple
    "f0:76:6f": "client",       # Apple
    "f0:98:9d": "client",       # Apple
    "f0:b0:e7": "client",       # Apple
    "f0:c1:f1": "client",       # Apple
    "f0:d1:a9": "client",       # Apple
    "f0:dc:e2": "client",       # Apple
    "f0:f6:1c": "client",       # Apple
    "f4:37:b7": "client",       # Apple
    "f4:5c:89": "client",       # Apple
    "f4:6b:ef": "client",       # Apple
    "f4:db:ed": "client",       # Apple
    "f4:f1:5a": "client",       # Apple
    "f4:f9:51": "client",       # Apple
    "f8:1e:df": "client",       # Apple
    "f8:27:93": "client",       # Apple
    "f8:2d:7c": "client",       # Apple
    "f8:6f:c1": "client",       # Apple
    "f8:72:ea": "client",       # Apple
    "f8:c3:cc": "client",       # Apple
    "f8:d0:27": "client",       # Apple
    "f8:ff:0b": "client",       # Apple
    "fc:25:3f": "client",       # Apple
    "fc:9b:c6": "client",       # Apple
    "fc:e9:98": "client",       # Apple

    # Samsung
    "00:07:ab": "client",       # Samsung
    "00:12:47": "client",       # Samsung
    "00:15:99": "client",       # Samsung
    "00:16:32": "client",       # Samsung
    "00:17:d5": "client",       # Samsung
    "00:18:af": "client",       # Samsung
    "00:1a:8a": "client",       # Samsung
    "00:1b:98": "client",       # Samsung
    "00:1c:43": "client",       # Samsung
    "00:1d:25": "client",       # Samsung
    "00:1e:e1": "client",       # Samsung
    "00:1e:e2": "client",       # Samsung
    "00:21:19": "client",       # Samsung
    "00:21:d1": "client",       # Samsung
    "00:23:39": "client",       # Samsung
    "00:23:3a": "client",       # Samsung
    "00:23:99": "client",       # Samsung
    "00:23:d6": "client",       # Samsung
    "00:23:d7": "client",       # Samsung
    "00:24:54": "client",       # Samsung
    "00:24:90": "client",       # Samsung
    "00:24:91": "client",       # Samsung
    "00:25:66": "client",       # Samsung
    "00:25:67": "client",       # Samsung
    "00:26:37": "client",       # Samsung
    "04:18:0f": "client",       # Samsung
    "08:d4:2b": "client",       # Samsung
    "08:fc:88": "client",       # Samsung
    "0c:14:20": "client",       # Samsung
    "0c:71:5d": "client",       # Samsung
    "10:05:b1": "client",       # Samsung
    "10:1d:c0": "client",       # Samsung
    "10:30:47": "client",       # Samsung
    "10:7b:44": "client",       # Samsung
    "10:d5:42": "client",       # Samsung
    "14:07:08": "client",       # Samsung
    "14:3e:bf": "client",       # Samsung
    "14:49:78": "client",       # Samsung
    "14:56:8e": "client",       # Samsung
    "14:89:fd": "client",       # Samsung
    "14:9f:3c": "client",       # Samsung
    "18:22:7e": "client",       # Samsung
    "18:67:b0": "client",       # Samsung
    "1c:62:b8": "client",       # Samsung
    "1c:af:f7": "client",       # Samsung
    "20:13:e0": "client",       # Samsung
    "20:55:31": "client",       # Samsung
    "20:64:32": "client",       # Samsung
    "20:6e:9c": "client",       # Samsung
    "20:a1:0e": "client",       # Samsung
    "20:d3:90": "client",       # Samsung
    "20:db:ab": "client",       # Samsung
    "24:05:0f": "client",       # Samsung
    "24:4b:03": "client",       # Samsung
    "24:4b:81": "client",       # Samsung
    "24:92:0e": "client",       # Samsung
    "24:c6:96": "client",       # Samsung
    "28:27:bf": "client",       # Samsung
    "28:39:26": "client",       # Samsung
    "28:3c:e4": "client",       # Samsung
    "28:56:5a": "client",       # Samsung
    "28:6a:ba": "client",       # Samsung
    "28:83:c9": "client",       # Samsung
    "28:98:7b": "client",       # Samsung
    "28:ba:b5": "client",       # Samsung
    "28:cc:01": "client",       # Samsung
    "2c:ae:2b": "client",       # Samsung
    "30:07:4d": "client",       # Samsung
    "30:19:66": "client",       # Samsung
    "30:3a:64": "client",       # Samsung
    "30:76:6f": "client",       # Samsung
    "30:96:fb": "client",       # Samsung
    "30:cd:a7": "client",       # Samsung
    "30:d6:c9": "client",       # Samsung
    "34:13:a8": "client",       # Samsung
    "34:23:ba": "client",       # Samsung
    "34:38:b7": "client",       # Samsung
    "34:4b:50": "client",       # Samsung
    "34:5d:9e": "client",       # Samsung
    "34:6a:c2": "client",       # Samsung
    "34:7e:5c": "client",       # Samsung
    "34:8a:7b": "client",       # Samsung
    "34:aa:8b": "client",       # Samsung
    "34:c3:ac": "client",       # Samsung
    "38:01:97": "client",       # Samsung
    "38:0a:94": "client",       # Samsung
    "38:0b:40": "client",       # Samsung
    "38:16:d1": "client",       # Samsung
    "38:2d:d1": "client",       # Samsung
    "38:2e:18": "client",       # Samsung
    "38:7a:0e": "client",       # Samsung
    "38:94:ed": "client",       # Samsung
    "38:9a:f6": "client",       # Samsung
    "38:ec:e4": "client",       # Samsung
    "38:f8:89": "client",       # Samsung
    "3c:05:18": "client",       # Samsung
    "3c:28:6d": "client",       # Samsung
    "3c:5a:37": "client",       # Samsung
    "3c:6a:9d": "client",       # Samsung
    "3c:8b:fe": "client",       # Samsung
    "3c:91:2b": "client",       # Samsung
    "3c:9a:37": "client",       # Samsung
    "3c:ac:de": "client",       # Samsung
    "3c:bd:d8": "client",       # Samsung
    "3c:f3:92": "client",       # Samsung
    "3c:f7:a4": "client",       # Samsung
    "40:0e:85": "client",       # Samsung
    "40:11:dc": "client",       # Samsung
    "40:4e:36": "client",       # Samsung
    "40:5c:fd": "client",       # Samsung
    "40:78:6a": "client",       # Samsung
    "40:8b:07": "client",       # Samsung
    "40:9c:28": "client",       # Samsung
    "40:a6:e8": "client",       # Samsung
    "40:b8:9a": "client",       # Samsung
    "40:d3:ae": "client",       # Samsung
    "40:f3:08": "client",       # Samsung
    "44:00:4d": "client",       # Samsung
    "44:4e:6d": "client",       # Samsung
    "44:5e:cd": "client",       # Samsung
    "44:6d:6c": "client",       # Samsung
    "44:78:3e": "client",       # Samsung
    "44:f4:36": "client",       # Samsung
    "48:13:7e": "client",       # Samsung
    "48:27:ea": "client",       # Samsung
    "48:2c:a0": "client",       # Samsung
    "48:44:f7": "client",       # Samsung
    "48:51:b7": "client",       # Samsung
    "48:c7:96": "client",       # Samsung
    "48:e1:af": "client",       # Samsung
    "4c:3c:16": "client",       # Samsung
    "4c:66:41": "client",       # Samsung
    "4c:77:66": "client",       # Samsung
    "4c:a5:6d": "client",       # Samsung
    "4c:bc:a5": "client",       # Samsung
    "50:01:bb": "client",       # Samsung
    "50:32:75": "client",       # Samsung
    "50:56:a8": "client",       # Samsung
    "50:77:05": "client",       # Samsung
    "50:a4:c8": "client",       # Samsung
    "50:f5:20": "client",       # Samsung
    "50:fc:9f": "client",       # Samsung
    "54:40:ad": "client",       # Samsung
    "54:51:46": "client",       # Samsung
    "54:88:0e": "client",       # Samsung
    "54:92:be": "client",       # Samsung
    "54:9b:12": "client",       # Samsung
    "54:bd:79": "client",       # Samsung
    "54:fa:3e": "client",       # Samsung
    "58:c3:8b": "client",       # Samsung
    "5c:0a:5b": "client",       # Samsung
    "5c:2e:59": "client",       # Samsung
    "5c:3a:45": "client",       # Samsung
    "5c:3c:27": "client",       # Samsung
    "5c:49:79": "client",       # Samsung
    "5c:57:1a": "client",       # Samsung
    "5c:57:c8": "client",       # Samsung
    "5c:5b:ad": "client",       # Samsung
    "5c:70:17": "client",       # Samsung
    "5c:7d:5e": "client",       # Samsung
    "5c:97:f3": "client",       # Samsung
    "5c:a3:9d": "client",       # Samsung
    "5c:b5:24": "client",       # Samsung
    "5c:c6:d0": "client",       # Samsung
    "5c:f6:db": "client",       # Samsung
    "60:6b:bd": "client",       # Samsung
    "60:7e:cd": "client",       # Samsung
    "60:8f:5c": "client",       # Samsung
    "60:a1:0a": "client",       # Samsung
    "60:aa:db": "client",       # Samsung
    "60:c5:e8": "client",       # Samsung
    "60:d0:2c": "client",       # Samsung
    "60:f1:89": "client",       # Samsung
    "64:3f:5f": "client",       # Samsung
    "64:5d:92": "client",       # Samsung
    "64:77:91": "client",       # Samsung
    "64:7b:d4": "client",       # Samsung
    "64:87:d7": "client",       # Samsung
    "64:9c:81": "client",       # Samsung
    "64:b3:10": "client",       # Samsung
    "64:d2:c4": "client",       # Samsung
    "68:27:37": "client",       # Samsung
    "68:48:98": "client",       # Samsung
    "68:54:fd": "client",       # Samsung
    "68:57:2d": "client",       # Samsung
    "68:8a:f0": "client",       # Samsung
    "68:b8:d9": "client",       # Samsung
    "68:c4:4c": "client",       # Samsung
    "68:eb:ae": "client",       # Samsung
    "68:f0:b5": "client",       # Samsung
    "6c:0b:84": "client",       # Samsung
    "6c:14:14": "client",       # Samsung
    "6c:2f:2c": "client",       # Samsung
    "6c:5a:b0": "client",       # Samsung
    "6c:63:9c": "client",       # Samsung
    "6c:76:60": "client",       # Samsung
    "6c:8b:d3": "client",       # Samsung
    "6c:94:66": "client",       # Samsung
    "6c:f3:73": "client",       # Samsung
    "6c:f3:7f": "client",       # Samsung
    "70:05:14": "client",       # Samsung
    "70:26:05": "client",       # Samsung
    "70:4a:ae": "client",       # Samsung
    "70:5a:0f": "client",       # Samsung
    "70:66:1b": "client",       # Samsung
    "70:85:c6": "client",       # Samsung
    "70:8c:b6": "client",       # Samsung
    "70:9e:29": "client",       # Samsung
    "70:a8:e3": "client",       # Samsung
    "70:f9:27": "client",       # Samsung
    "74:45:ce": "client",       # Samsung
    "74:58:f3": "client",       # Samsung
    "74:78:18": "client",       # Samsung
    "74:a0:63": "client",       # Samsung
    "74:b5:7e": "client",       # Samsung
    "78:3f:15": "client",       # Samsung
    "78:40:e4": "client",       # Samsung
    "78:52:1a": "client",       # Samsung
    "78:59:5e": "client",       # Samsung
    "78:6a:18": "client",       # Samsung
    "78:9f:70": "client",       # Samsung
    "78:bd:bc": "client",       # Samsung
    "78:c3:e9": "client",       # Samsung
    "78:d6:f0": "client",       # Samsung
    "78:f7:be": "client",       # Samsung
    "7c:0b:c6": "client",       # Samsung
    "7c:14:76": "client",       # Samsung
    "7c:2e:0d": "client",       # Samsung
    "7c:38:6c": "client",       # Samsung
    "7c:49:eb": "client",       # Samsung
    "7c:61:66": "client",       # Samsung
    "7c:64:56": "client",       # Samsung
    "7c:71:c9": "client",       # Samsung
    "7c:8b:ca": "client",       # Samsung
    "7c:8b:de": "client",       # Samsung
    "7c:91:22": "client",       # Samsung
    "7c:94:b2": "client",       # Samsung
    "7c:a1:ae": "client",       # Samsung
    "7c:a2:9b": "client",       # Samsung
    "7c:a9:7d": "client",       # Samsung
    "7c:b5:9b": "client",       # Samsung
    "7c:f8:80": "client",       # Samsung
    "80:65:6d": "client",       # Samsung
    "80:6c:1b": "client",       # Samsung
    "84:25:db": "client",       # Samsung
    "84:38:38": "client",       # Samsung
    "84:55:a5": "client",       # Samsung
    "84:79:73": "client",       # Samsung
    "84:a4:66": "client",       # Samsung
    "84:b1:53": "client",       # Samsung
    "84:b5:41": "client",       # Samsung
    "84:c7:ea": "client",       # Samsung
    "84:e5:40": "client",       # Samsung
    "88:1a:14": "client",       # Samsung
    "88:32:9b": "client",       # Samsung
    "88:50:dd": "client",       # Samsung
    "88:71:b1": "client",       # Samsung
    "88:83:22": "client",       # Samsung
    "88:9b:39": "client",       # Samsung
    "88:bd:45": "client",       # Samsung
    "88:c9:d0": "client",       # Samsung
    "8c:71:f8": "client",       # Samsung
    "8c:77:12": "client",       # Samsung
    "8c:79:67": "client",       # Samsung
    "8c:7b:90": "client",       # Samsung
    "8c:84:01": "client",       # Samsung
    "8c:8a:6e": "client",       # Samsung
    "8c:8e:76": "client",       # Samsung
    "8c:f5:a3": "client",       # Samsung
    "90:00:4e": "client",       # Samsung
    "90:18:7c": "client",       # Samsung
    "90:6c:ac": "client",       # Samsung
    "90:f1:aa": "client",       # Samsung
    "94:01:c2": "client",       # Samsung
    "94:35:0a": "client",       # Samsung
    "94:47:88": "client",       # Samsung
    "94:51:03": "client",       # Samsung
    "94:54:c5": "client",       # Samsung
    "94:7b:e7": "client",       # Samsung
    "94:b2:cc": "client",       # Samsung
    "94:b8:6d": "client",       # Samsung
    "94:d0:29": "client",       # Samsung
    "94:d7:71": "client",       # Samsung
    "94:db:c9": "client",       # Samsung
    "94:e3:ee": "client",       # Samsung
    "94:e7:ea": "client",       # Samsung
    "98:0c:82": "client",       # Samsung
    "98:4b:4a": "client",       # Samsung
    "98:52:b1": "client",       # Samsung
    "98:58:8a": "client",       # Samsung
    "98:83:89": "client",       # Samsung
    "98:c5:db": "client",       # Samsung
    "98:f5:a9": "client",       # Samsung
    "9c:02:98": "client",       # Samsung
    "9c:3a:af": "client",       # Samsung
    "9c:4f:da": "client",       # Samsung
    "9c:5c:8d": "client",       # Samsung
    "9c:65:b0": "client",       # Samsung
    "9c:8e:9c": "client",       # Samsung
    "9c:b7:0d": "client",       # Samsung
    "9c:d3:5b": "client",       # Samsung
    "9c:f6:dd": "client",       # Samsung
    "a0:07:98": "client",       # Samsung
    "a0:0b:ba": "client",       # Samsung
    "a0:10:81": "client",       # Samsung
    "a0:39:f7": "client",       # Samsung
    "a0:56:f3": "client",       # Samsung
    "a0:5d:c1": "client",       # Samsung
    "a0:78:ba": "client",       # Samsung
    "a0:82:1f": "client",       # Samsung
    "a0:8c:9b": "client",       # Samsung
    "a0:9d:86": "client",       # Samsung
    "a0:b4:37": "client",       # Samsung
    "a0:b4:a5": "client",       # Samsung
    "a0:c5:89": "client",       # Samsung
    "a0:d0:dc": "client",       # Amazon
    "a4:07:b6": "client",       # Samsung
    "a4:30:7a": "client",       # Samsung
    "a4:44:f1": "client",       # Samsung
    "a4:6c:c1": "client",       # Samsung
    "a4:c6:4f": "client",       # Samsung
    "a8:06:00": "client",       # Samsung
    "a8:2b:b5": "client",       # Samsung
    "a8:51:6b": "client",       # Samsung
    "a8:55:6a": "client",       # Samsung
    "a8:62:a2": "client",       # Samsung
    "a8:81:95": "client",       # Samsung
    "a8:9c:a4": "client",       # Samsung
    "a8:b8:6e": "client",       # Samsung
    "a8:c8:3a": "client",       # Samsung
    "a8:db:03": "client",       # Samsung
    "a8:e7:7d": "client",       # Samsung
    "a8:f5:ac": "client",       # Samsung
    "ac:36:13": "client",       # Samsung
    "ac:44:f2": "client",       # Samsung
    "ac:5a:14": "client",       # Samsung
    "ac:5f:3e": "client",       # Samsung
    "ac:67:5d": "client",       # Samsung
    "ac:7a:56": "client",       # Samsung
    "ac:89:c2": "client",       # Samsung
    "ac:cf:85": "client",       # Samsung
    "ac:e8:7b": "client",       # Samsung
    "b0:47:bf": "client",       # Samsung
    "b0:72:bf": "client",       # Samsung
    "b0:7f:b9": "client",       # Samsung
    "b0:91:22": "client",       # Samsung
    "b0:ec:71": "client",       # Samsung
    "b0:f1:ec": "client",       # Samsung
    "b4:3a:28": "client",       # Samsung
    "b4:79:c8": "client",       # Samsung
    "b4:7a:f1": "client",       # Samsung
    "b4:9e:ac": "client",       # Samsung
    "b4:bf:f6": "client",       # Samsung
    "b8:16:db": "client",       # Samsung
    "b8:57:76": "client",       # Samsung
    "b8:5e:7b": "client",       # Samsung
    "b8:62:1f": "client",       # Samsung
    "b8:79:3e": "client",       # Samsung
    "b8:86:87": "client",       # Samsung
    "b8:8a:ec": "client",       # Samsung
    "b8:bc:5b": "client",       # Samsung
    "b8:c1:11": "client",       # Samsung
    "b8:d4:3d": "client",       # Samsung
    "b8:d9:ce": "client",       # Samsung
    "bc:14:01": "client",       # Samsung
    "bc:14:85": "client",       # Samsung
    "bc:20:a4": "client",       # Samsung
    "bc:3e:13": "client",       # Samsung
    "bc:44:86": "client",       # Samsung
    "bc:47:60": "client",       # Samsung
    "bc:54:f9": "client",       # Samsung
    "bc:72:b1": "client",       # Samsung
    "bc:76:70": "client",       # Samsung
    "bc:77:9f": "client",       # Samsung
    "bc:79:ad": "client",       # Samsung
    "bc:85:1f": "client",       # Samsung
    "bc:8a:a8": "client",       # Samsung
    "bc:8b:b3": "client",       # Samsung
    "bc:97:40": "client",       # Samsung
    "bc:98:df": "client",       # Samsung
    "bc:9c:c1": "client",       # Samsung
    "bc:a5:8b": "client",       # Samsung
    "bc:b0:e7": "client",       # Samsung
    "bc:b3:08": "client",       # Samsung
    "bc:d1:1f": "client",       # Samsung
    "bc:f2:af": "client",       # Samsung
    "bc:f5:ac": "client",       # Samsung
    "bc:f6:1c": "client",       # Samsung
    "bc:fe:d9": "client",       # Samsung
    "c0:11:a6": "client",       # Samsung
    "c0:48:e6": "client",       # Samsung
    "c0:97:27": "client",       # Samsung
    "c0:bd:c1": "client",       # Samsung
    "c0:cb:38": "client",       # Samsung
    "c0:ce:cd": "client",       # Samsung
    "c0:d3:91": "client",       # Samsung
    "c0:e4:2d": "client",       # Samsung
    "c0:e8:62": "client",       # Samsung
    "c4:12:f5": "client",       # Samsung
    "c4:42:02": "client",       # Samsung
    "c4:44:7d": "client",       # Samsung
    "c4:57:6e": "client",       # Samsung
    "c4:73:1e": "client",       # Samsung
    "c4:98:80": "client",       # Samsung
    "c4:9f:4c": "client",       # Samsung
    "c4:a3:66": "client",       # Samsung
    "c4:b9:cd": "client",       # Cisco
    "c4:ba:99": "client",       # Samsung
    "c4:e0:32": "client",       # Samsung
    "c8:14:51": "client",       # Samsung
    "c8:19:f7": "client",       # Samsung
    "c8:29:2a": "client",       # Samsung
    "c8:38:70": "client",       # Samsung
    "c8:3e:99": "client",       # Samsung
    "c8:58:c0": "client",       # Samsung
    "c8:64:c7": "client",       # Samsung
    "c8:77:68": "client",       # Samsung
    "c8:89:f3": "client",       # Samsung
    "c8:8a:1a": "client",       # Samsung
    "c8:93:46": "client",       # Samsung
    "c8:94:bb": "client",       # Samsung
    "c8:ba:94": "client",       # Samsung
    "c8:bd:4d": "client",       # Samsung
    "c8:d1:2a": "client",       # Samsung
    "c8:e0:eb": "client",       # Samsung
    "c8:f7:42": "client",       # Samsung
    "cc:07:ab": "client",       # Samsung
    "cc:20:e8": "client",       # Samsung
    "cc:3a:61": "client",       # Samsung
    "cc:4e:ec": "client",       # Samsung
    "cc:61:e5": "client",       # Samsung
    "cc:69:b0": "client",       # Samsung
    "cc:7a:a4": "client",       # Samsung
    "cc:7b:35": "client",       # Samsung
    "d0:22:be": "client",       # Samsung
    "d0:25:98": "client",       # Samsung
    "d0:54:2a": "client",       # Samsung
    "d0:57:7b": "client",       # Samsung
    "d0:59:f3": "client",       # Samsung
    "d0:66:7b": "client",       # Samsung
    "d0:6a:1f": "client",       # Samsung
    "d0:7d:33": "client",       # Samsung
    "d0:87:e2": "client",       # Samsung
    "d0:8a:91": "client",       # Samsung
    "d0:93:f0": "client",       # Samsung
    "d0:94:66": "client",       # Samsung
    "d0:9c:30": "client",       # Samsung
    "d0:a4:b1": "client",       # Samsung
    "d0:c1:b1": "client",       # Samsung
    "d0:d7:83": "client",       # Samsung
    "d0:db:32": "client",       # Samsung
    "d0:e7:82": "client",       # Samsung
    "d4:3d:2e": "client",       # Samsung
    "d4:53:af": "client",       # Samsung
    "d4:85:64": "client",       # Samsung
    "d4:88:90": "client",       # Samsung
    "d4:91:0f": "client",       # Samsung
    "d4:a1:48": "client",       # Samsung
    "d4:ae:05": "client",       # Samsung
    "d4:d2:52": "client",       # Samsung
    "d8:0f:99": "client",       # Samsung
    "d8:14:df": "client",       # Samsung
    "d8:16:c1": "client",       # Samsung
    "d8:19:ce": "client",       # Samsung
    "d8:24:bd": "client",       # Samsung
    "d8:28:c9": "client",       # Samsung
    "d8:30:62": "client",       # Samsung
    "d8:31:cf": "client",       # Samsung
    "d8:54:3a": "client",       # Samsung
    "d8:57:7a": "client",       # Samsung
    "d8:5b:2a": "client",       # Samsung
    "d8:5d:4c": "client",       # Samsung
    "d8:5d:84": "client",       # Samsung
    "d8:61:94": "client",       # Samsung
    "d8:88:ce": "client",       # Samsung
    "d8:90:e8": "client",       # Samsung
    "d8:96:e0": "client",       # Samsung
    "d8:97:3b": "client",       # Samsung
    "d8:a0:1d": "client",       # Samsung
    "d8:ab:84": "client",       # Samsung
    "d8:c4:6a": "client",       # Samsung
    "d8:c4:e9": "client",       # Samsung
    "d8:d4:3c": "client",       # Samsung
    "d8:dc:d4": "client",       # Samsung
    "d8:e0:04": "client",       # Samsung
    "d8:e0:e1": "client",       # Samsung
    "d8:e7:2b": "client",       # Samsung
    "d8:ef:cd": "client",       # Samsung
    "d8:f3:bc": "client",       # Samsung
    "dc:0b:34": "client",       # Samsung
    "dc:1b:a1": "client",       # Samsung
    "dc:3e:51": "client",       # Samsung
    "dc:4e:de": "client",       # Samsung
    "dc:5e:26": "client",       # Samsung
    "dc:66:72": "client",       # Samsung
    "dc:6d:cd": "client",       # Samsung
    "dc:71:44": "client",       # Samsung
    "dc:7b:94": "client",       # Samsung
    "dc:8b:28": "client",       # Samsung
    "dc:9a:8e": "client",       # Samsung
    "dc:d2:fc": "client",       # Samsung
    "dc:d9:16": "client",       # Samsung
    "dc:e5:78": "client",       # Samsung
    "dc:f7:19": "client",       # Samsung
    "e0:1d:3b": "client",       # Samsung
    "e0:24:7f": "client",       # Samsung
    "e0:48:d3": "client",       # Samsung
    "e0:5f:45": "client",       # Samsung
    "e0:75:0a": "client",       # Samsung
    "e0:97:96": "client",       # Samsung
    "e0:99:71": "client",       # Samsung
    "e0:9d:b8": "client",       # Samsung
    "e0:a1:98": "client",       # Samsung
    "e0:a3:60": "client",       # Samsung
    "e0:a6:70": "client",       # Samsung
    "e0:aa:b0": "client",       # Samsung
    "e0:ac:f1": "client",       # Samsung
    "e0:b2:60": "client",       # Samsung
    "e0:b9:4d": "client",       # Samsung
    "e0:cb:1d": "client",       # Samsung
    "e0:cb:ee": "client",       # Samsung
    "e0:db:10": "client",       # Samsung
    "e4:12:18": "client",       # Samsung
    "e4:12:89": "client",       # Samsung
    "e4:1c:4b": "client",       # Samsung
    "e4:55:ea": "client",       # Samsung
    "e4:58:e8": "client",       # Samsung
    "e4:5c:f5": "client",       # Samsung
    "e4:6c:21": "client",       # Samsung
    "e4:76:18": "client",       # Samsung
    "e4:7b:3f": "client",       # Samsung
    "e4:7c:f9": "client",       # Samsung
    "e4:7e:9a": "client",       # Samsung
    "e4:8d:8c": "client",       # Samsung
    "e4:90:fd": "client",       # Samsung
    "e4:92:fb": "client",       # Samsung
    "e4:98:d1": "client",       # Samsung
    "e4:a7:a0": "client",       # Samsung
    "e4:aa:5d": "client",       # Samsung
    "e4:b0:21": "client",       # Samsung
    "e4:bd:4b": "client",       # Samsung
    "e4:c2:d1": "client",       # Samsung
    "e4:d1:24": "client",       # Samsung
    "e4:d3:aa": "client",       # Samsung
    "e4:e0:c5": "client",       # Samsung
    "e4:e3:aa": "client",       # Samsung
    "e4:f0:42": "client",       # Google
    "e8:04:62": "client",       # Samsung
    "e8:06:88": "client",       # Samsung
    "e8:0f:c8": "client",       # Samsung
    "e8:11:32": "client",       # Samsung
    "e8:28:19": "client",       # Samsung
    "e8:3a:4b": "client",       # Samsung
    "e8:3e:fc": "client",       # Samsung
    "e8:50:8b": "client",       # Samsung
    "e8:5a:8b": "client",       # Samsung
    "e8:5b:5b": "client",       # Samsung
    "e8:65:5f": "client",       # Samsung
    "e8:6f:38": "client",       # Samsung
    "e8:78:29": "client",       # Samsung
    "e8:82:5b": "client",       # Samsung
    "e8:8d:f5": "client",       # Samsung
    "e8:91:20": "client",       # Samsung
    "e8:98:c2": "client",       # Samsung
    "e8:a7:88": "client",       # Samsung
    "e8:b1:fc": "client",       # Samsung
    "e8:be:81": "client",       # Samsung
    "e8:c1:45": "client",       # Samsung
    "e8:c2:29": "client",       # Samsung
    "e8:c3:20": "client",       # Samsung
    "e8:cc:18": "client",       # Samsung
    "e8:d0:3c": "client",       # Samsung
    "e8:d0:fa": "client",       # Samsung
    "e8:e5:d6": "client",       # Samsung
    "e8:ea:6a": "client",       # Samsung
    "e8:f2:26": "client",       # Samsung
    "e8:f2:e2": "client",       # Samsung
    "ec:01:33": "client",       # Samsung
    "ec:01:ee": "client",       # Samsung
    "ec:0e:cb": "client",       # Samsung
    "ec:1b:bd": "client",       # Samsung
    "ec:1f:72": "client",       # Samsung
    "ec:26:ca": "client",       # Samsung
    "ec:3e:b3": "client",       # Samsung
    "ec:47:3c": "client",       # Samsung
    "ec:55:f9": "client",       # Samsung
    "ec:64:b8": "client",       # Samsung
    "ec:6c:9a": "client",       # Samsung
    "ec:71:db": "client",       # Samsung
    "ec:74:ba": "client",       # Samsung
    "ec:89:14": "client",       # Samsung
    "ec:91:61": "client",       # Samsung
    "ec:98:c1": "client",       # Samsung
    "ec:9b:8b": "client",       # Samsung
    "ec:9c:12": "client",       # Samsung
    "ec:a8:19": "client",       # Samsung
    "ec:ad:b8": "client",       # Samsung
    "ec:b5:41": "client",       # Samsung
    "ec:b8:70": "client",       # Samsung
    "ec:ba:86": "client",       # Samsung
    "ec:bb:ae": "client",       # Samsung
    "ec:be:5f": "client",       # Samsung
    "ec:bf:d0": "client",       # Samsung
    "ec:c0:1e": "client",       # Samsung
    "ec:c3:02": "client",       # Samsung
    "ec:c7:a6": "client",       # Samsung
    "ec:cb:68": "client",       # Samsung
    "ec:d0:0e": "client",       # Samsung
    "ec:d0:9f": "client",       # Samsung
    "ec:d6:8a": "client",       # Samsung
    "ec:e0:9b": "client",       # Samsung
    "ec:f0:0e": "client",       # Samsung
    "ec:f3:42": "client",       # Samsung
    "ec:f3:5b": "client",       # Samsung
    "ec:f4:bb": "client",       # Samsung
    "f0:03:8c": "client",       # Samsung
    "f0:08:d1": "client",       # Samsung
    "f0:25:b7": "client",       # Samsung
    "f0:27:45": "client",       # Samsung
    "f0:2a:63": "client",       # Samsung
    "f0:5a:09": "client",       # Samsung
    "f0:5b:7b": "client",       # Samsung
    "f0:62:81": "client",       # Samsung
    "f0:7b:cb": "client",       # Samsung
    "f0:7f:0c": "client",       # Samsung
    "f0:82:61": "client",       # Samsung
    "f0:99:b6": "client",       # Apple
    "f0:d7:aa": "client",       # Samsung
    "f0:db:e2": "client",       # Samsung
    "f0:db:f8": "client",       # Samsung
    "f0:e7:7e": "client",       # Samsung
    "f0:ee:10": "client",       # Samsung
    "f4:09:d8": "client",       # Samsung
    "f4:0e:22": "client",       # Samsung
    "f4:1b:a1": "client",       # Samsung
    "f4:2b:7d": "client",       # Samsung
    "f4:3e:66": "client",       # Samsung
    "f4:42:89": "client",       # Samsung
    "f4:42:ed": "client",       # Samsung
    "f4:4b:2a": "client",       # Samsung
    "f4:55:9c": "client",       # Samsung
    "f4:5e:ab": "client",       # Samsung
    "f4:63:1f": "client",       # Samsung
    "f4:7b:5e": "client",       # Samsung
    "f4:96:51": "client",       # Samsung
    "f4:9f:f3": "client",       # Samsung
    "f4:a7:88": "client",       # Samsung
    "f4:c2:48": "client",       # Samsung
    "f4:d4:88": "client",       # Samsung
    "f4:d9:fb": "client",       # Samsung
    "f4:e3:fb": "client",       # Samsung
    "f4:e9:d4": "client",       # Samsung
    "f8:04:2e": "client",       # Samsung
    "f8:0f:41": "client",       # Samsung
    "f8:0f:84": "client",       # Samsung
    "f8:24:41": "client",       # Samsung
    "f8:3d:ff": "client",       # Samsung
    "f8:44:e3": "client",       # Samsung
    "f8:45:dd": "client",       # Samsung
    "f8:4f:ad": "client",       # Samsung
    "f8:54:b8": "client",       # Samsung
    "f8:5b:6e": "client",       # Samsung
    "f8:64:65": "client",       # Samsung
    "f8:6c:e1": "client",       # Samsung
    "f8:7f:a4": "client",       # Samsung
    "f8:84:f9": "client",       # Samsung
    "f8:89:d2": "client",       # Samsung
    "f8:8e:a1": "client",       # Samsung
    "f8:8f:ca": "client",       # Samsung
    "f8:94:c2": "client",       # Samsung
    "f8:a9:63": "client",       # Samsung
    "f8:bf:09": "client",       # Samsung
    "f8:c0:91": "client",       # Samsung
    "f8:c1:16": "client",       # Samsung
    "f8:d1:11": "client",       # Samsung
    "f8:e6:1a": "client",       # Samsung
    "f8:e8:11": "client",       # Samsung
    "f8:e9:4e": "client",       # Samsung
    "fc:00:13": "client",       # Samsung
    "fc:07:a0": "client",       # Samsung
    "fc:0f:e6": "client",       # Samsung
    "fc:19:10": "client",       # Samsung
    "fc:1f:19": "client",       # Samsung
    "fc:2a:54": "client",       # Samsung
    "fc:3f:7c": "client",       # Samsung
    "fc:42:03": "client",       # Samsung
    "fc:44:82": "client",       # Samsung
    "fc:4b:bc": "client",       # Samsung
    "fc:5a:1d": "client",       # Samsung
    "fc:62:6e": "client",       # Samsung
    "fc:69:4c": "client",       # Samsung
    "fc:71:fa": "client",       # Samsung
    "fc:7f:f1": "client",       # Samsung
    "fc:87:43": "client",       # Samsung
    "fc:8e:6e": "client",       # Samsung
    "fc:8f:7d": "client",       # Samsung
    "fc:92:3b": "client",       # Samsung
    "fc:a1:3e": "client",       # Samsung
    "fc:a6:21": "client",       # Amazon (Echo)
    "fc:a6:67": "client",       # Amazon
    "fc:ab:90": "client",       # Samsung
    "fc:b0:de": "client",       # Samsung
    "fc:b3:bc": "client",       # Samsung
    "fc:ba:c0": "client",       # Samsung
    "fc:be:7b": "client",       # Samsung
    "fc:c0:03": "client",       # Samsung
    "fc:c2:de": "client",       # Samsung
    "fc:d6:bd": "client",       # Samsung
    "fc:e2:6c": "client",       # Samsung
    "fc:e3:3c": "client",       # Samsung
    "fc:ea:58": "client",       # Samsung
    "fc:ee:e6": "client",       # Samsung
    "fc:f1:36": "client",       # Samsung
    "fc:f1:52": "client",       # Samsung
    "fc:f5:28": "client",       # Samsung
    "fc:f7:7b": "client",       # Samsung
    "fc:f8:ae": "client",       # Samsung

    # Xiaomi
    "28:6c:07": "client",       # Xiaomi
    "34:ce:00": "client",       # Xiaomi
    "58:44:98": "client",       # Xiaomi
    "64:b4:73": "client",       # Xiaomi
    "64:cc:2e": "client",       # Xiaomi
    "6c:1d:eb": "client",       # Xiaomi
    "74:23:44": "client",       # Xiaomi
    "74:51:ba": "client",       # Xiaomi
    "78:11:dc": "client",       # Xiaomi
    "78:25:ad": "client",       # Xiaomi
    "7c:1c:68": "client",       # Xiaomi
    "7c:78:b2": "client",       # Xiaomi
    "8c:de:f9": "client",       # Xiaomi
    "94:65:2d": "client",       # OnePlus (Xiaomi subsidiary)
    "a4:08:ea": "client",       # Xiaomi
    "ac:c1:ee": "client",       # Xiaomi
    "ac:f7:f3": "client",       # Xiaomi
    "b0:e2:35": "client",       # Xiaomi
    "b8:57:d8": "client",       # Xiaomi
    "c4:0b:cb": "client",       # Xiaomi
    "c4:6a:b7": "client",       # Xiaomi
    "d4:97:0b": "client",       # Xiaomi
    "f0:b4:29": "client",       # Xiaomi
    "f4:8b:32": "client",       # Xiaomi
    "f8:a4:5f": "client",       # Xiaomi

    # Google
    "3c:5a:b8": "client",       # Google
    "54:60:09": "client",       # Google
    "f4:f5:d8": "client",       # Google
    "f4:60:77": "client",       # Google
    "a4:77:33": "client",       # Google
    "54:03:f5": "client",       # Google Nest

    # Amazon (Echo, Fire TV, Kindle)
    "fc:65:de": "client",       # Amazon
    "f0:27:2d": "client",       # Amazon
    "68:37:e9": "client",       # Amazon
    "74:c2:46": "client",       # Amazon
    "84:7a:88": "client",       # Amazon
    "a0:02:dc": "client",       # Amazon

    # Microsoft / Xbox
    "7c:1e:52": "client",       # Microsoft
    "28:18:78": "client",       # Microsoft
    "00:15:5d": "client",       # Microsoft (Hyper-V)

    # Raspberry Pi
    "b8:27:eb": "server",       # Raspberry Pi (often used as servers)
    "dc:a6:32": "server",       # Raspberry Pi
    "e4:5f:01": "server",       # Raspberry Pi
    "d8:3a:dd": "server",       # Raspberry Pi

    # ── Common generic ──
    "ff:ff:ff": "unknown",      # Broadcast
    "00:00:00": "unknown",      # Null

    # ── Home routers (common consumer brands) ──
    "e4:c3:2a": "router",       # TP-Link
    "50:c7:bf": "router",       # TP-Link
}


def _lookup_oui(mac: str) -> str | None:
    """Look up device type by MAC OUI prefix (first 3 bytes)."""
    if not mac or len(mac) < 8:
        return None
    prefix = mac[:8]  # "aa:bb:cc"
    return _OUI_PREFIXES.get(prefix)


# ── Per-IP Behavior Tracking ───────────────────────────────────────────

@dataclass
class _IpBehavior:
    """Tracks observed behavior for a single IP address."""
    macs: set[str] = field(default_factory=set)
    ports_as_server: set[int] = field(default_factory=set)  # ports this IP responds on
    ports_as_client: set[int] = field(default_factory=set)  # ports this IP connects to
    tcp_syn_sent: int = 0          # how many SYN packets sent (client behavior)
    tcp_syn_ack_sent: int = 0      # how many SYN+ACK packets sent (server behavior)
    tcp_rst_sent: int = 0          # RST packets sent (could be firewall)
    icmp_unreachable_sent: int = 0 # ICMP unreachable sent (router/firewall)
    arp_sent: int = 0              # ARP packets originated (routers ARP-scan their subnet)
    ttl_values: list[int] = field(default_factory=list)
    protocols: set[str] = field(default_factory=set)


def _is_real_mac(mac: str) -> bool:
    """Filter out broadcast, null, and multicast MACs — they carry no OUI signal."""
    if not mac:
        return False
    return not mac.startswith(("ff:ff:ff", "00:00:00", "01:00:5e", "33:33"))


def _collect_behavior(packets: list[RawPacket]) -> dict[str, _IpBehavior]:
    """Aggregate per-IP behavior from all packets. One pass — O(n)."""
    behaviors: dict[str, _IpBehavior] = {}

    for pkt in packets:
        # Source IP behavior
        if pkt.src_ip not in behaviors:
            behaviors[pkt.src_ip] = _IpBehavior()
        src_b = behaviors[pkt.src_ip]

        if _is_real_mac(pkt.src_mac):
            src_b.macs.add(pkt.src_mac)

        src_b.protocols.add(pkt.protocol)

        if pkt.ttl > 0:
            src_b.ttl_values.append(pkt.ttl)

        if pkt.tcp_flags:
            flags = pkt.tcp_flags.upper()
            if "S" in flags and "A" not in flags:
                src_b.tcp_syn_sent += 1
            if "S" in flags and "A" in flags:
                src_b.tcp_syn_ack_sent += 1
            if "R" in flags:
                src_b.tcp_rst_sent += 1

        if pkt.protocol == "ICMP" and pkt.headers.get("type") == 3:
            src_b.icmp_unreachable_sent += 1

        # ARP origination: routers ARP-scan/gratuitous-ARP their subnet.
        # Only count ARPs whose source MAC isn't broadcast (src is the asker).
        if pkt.protocol == "ARP" and pkt.src_mac and not pkt.src_mac.startswith("ff:ff:ff"):
            src_b.arp_sent += 1

        # Track ports: if src_port is low (< 1024), this IP is "serving" on it
        if pkt.src_port and pkt.src_port < 1024:
            src_b.ports_as_server.add(pkt.src_port)
        if pkt.dst_port and pkt.dst_port < 1024:
            src_b.ports_as_client.add(pkt.dst_port)

        # Destination IP behavior
        if pkt.dst_ip not in behaviors:
            behaviors[pkt.dst_ip] = _IpBehavior()
        dst_b = behaviors[pkt.dst_ip]

        if _is_real_mac(pkt.dst_mac):
            dst_b.macs.add(pkt.dst_mac)

    return behaviors


# ── Classification with Confidence ─────────────────────────────────────

# Cache: ip → (device_type, confidence)
_classification_cache: dict[str, tuple[str, float]] = {}


def classify_device(ip: str, behavior: _IpBehavior) -> tuple[str, float]:
    """Classify a device by IP using MAC OUI + observed behavior.

    Returns (device_type, confidence) where confidence is 0.0–1.0.
    Result is cached — each IP is classified only once.
    """
    # Check cache first
    if ip in _classification_cache:
        return _classification_cache[ip]

    oui_type: str | None = None
    behavior_type: str | None = None
    oui_confidence = 0.0
    behavior_confidence = 0.0

    # ── Step 1: MAC OUI lookup ──
    for mac in behavior.macs:
        result = _lookup_oui(mac)
        if result:
            oui_type = result
            oui_confidence = 0.7  # OUI is a strong signal
            break

    # ── Step 2: Header/behavior analysis ──

    # Server detection: responds with SYN+ACK on low ports
    if behavior.tcp_syn_ack_sent > behavior.tcp_syn_sent:
        behavior_type = "server"
        behavior_confidence = 0.8
    # Client detection: only sends SYN, never SYN+ACK
    elif behavior.tcp_syn_sent > 0 and behavior.tcp_syn_ack_sent == 0:
        behavior_type = "client"
        behavior_confidence = 0.6

    # Router detection: sends ICMP unreachable, has many low ports
    if behavior.icmp_unreachable_sent > 0:
        if behavior_type != "server":  # don't override server
            behavior_type = "router"
            behavior_confidence = 0.75

    # Firewall detection: lots of RST, no SYN+ACK
    if behavior.tcp_rst_sent > 5 and behavior.tcp_syn_ack_sent == 0:
        behavior_type = "firewall"
        behavior_confidence = 0.65

    # Specific port-based refinements
    if 53 in behavior.ports_as_server:
        behavior_type = "server"  # DNS server
        behavior_confidence = max(behavior_confidence, 0.7)
    if 80 in behavior.ports_as_server or 443 in behavior.ports_as_server:
        behavior_type = "server"  # Web server
        behavior_confidence = max(behavior_confidence, 0.7)
    if 67 in behavior.ports_as_server:
        if behavior_type != "server":
            behavior_type = "router"  # DHCP server
            behavior_confidence = max(behavior_confidence, 0.7)

    # Gateway convention: x.x.x.1 / x.x.x.254 is almost always the router.
    # Guard: real servers (SYN+ACK dominant) can also end in .1 (e.g. public DNS).
    if (
        (ip.endswith(".1") or ip.endswith(".254"))
        and behavior.tcp_syn_ack_sent <= behavior.tcp_syn_sent
    ):
        behavior_type = "router"
        behavior_confidence = max(behavior_confidence, 0.8)

    # ARP origination: routers ARP-scan / gratuitous-ARP their subnet.
    if behavior.arp_sent >= 3 and behavior_type in (None, "client"):
        behavior_type = "router"
        behavior_confidence = max(behavior_confidence, 0.7)

    # ── Step 3: Combine signals ──
    final_type = "unknown"
    final_confidence = 0.3

    if oui_type and behavior_type:
        # Both signals agree — high confidence
        if oui_type == behavior_type:
            final_type = oui_type
            final_confidence = min(1.0, (oui_confidence + behavior_confidence) / 2 + 0.2)
        # OUI says router/switch/firewall, behavior confirms server — trust OUI
        elif oui_type in ("router", "switch", "firewall") and behavior_type == "server":
            final_type = oui_type  # It's a router that also serves
            final_confidence = oui_confidence
        # Behavior overrides OUI for generic devices
        elif behavior_confidence > oui_confidence:
            final_type = behavior_type
            final_confidence = behavior_confidence
        else:
            final_type = oui_type
            final_confidence = oui_confidence
    elif oui_type:
        final_type = oui_type
        final_confidence = oui_confidence
    elif behavior_type:
        final_type = behavior_type
        final_confidence = behavior_confidence

    # ── Cache and return ──
    _classification_cache[ip] = (final_type, final_confidence)
    return final_type, final_confidence


def _local_prefix(ip: str) -> str | None:
    """Return the /24 prefix of a valid unicast IPv4 address, else None."""
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return None
    if ip in ("255.255.255.255", "0.0.0.0"):
        return None
    if ip.startswith(("224.", "239.")):  # multicast
        return None
    return ".".join(parts[:3])


def classify_all(packets: list[RawPacket]) -> dict[str, tuple[str, float]]:
    """Classify all unique IPs from packet data.

    Returns dict of ip → (device_type, confidence).
    Each IP is classified exactly once.

    MAC/OUI evidence is only trusted for IPs in the dominant (local) subnet:
    for remote IPs we only ever observe the router's MAC as L2 next-hop,
    never the remote host's own MAC.
    """
    global _classification_cache
    _classification_cache = {}  # Reset for each session

    behaviors = _collect_behavior(packets)

    # Infer local subnet from the dominant /24 prefix
    prefix_counts: Counter[str] = Counter(
        p for ip in behaviors if (p := _local_prefix(ip)) is not None
    )
    dominant = prefix_counts.most_common(1)[0][0] if prefix_counts else None

    # Strip MAC evidence from non-local IPs — it belongs to the router, not them
    if dominant:
        for ip, behavior in behaviors.items():
            if ip != dominant and not ip.startswith(dominant + "."):
                behavior.macs.clear()

    results: dict[str, tuple[str, float]] = {}

    for ip, behavior in behaviors.items():
        results[ip] = classify_device(ip, behavior)

    log.info(
        "Classified %d devices: %s",
        len(results),
        {
            t: sum(1 for v, _ in results.values() if v == t)
            for t in set(v for v, _ in results.values())
        },
    )

    return results