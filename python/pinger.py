# CRASH MONITOR - ROUTER PING LOOP
# TARGET: TP-Link Archer AX1450
# GOAL: detect when router crashes/stops responding during frame fuzzing
# run this on the second laptop connected to the router


# UI IMPORTS
from rich.console import Console
from rich.panel import Panel


# ETC IMPORTS
import subprocess, time
from datetime import datetime


# CONSTANTS
console = Console()


# ========================
#   CONFIG
# ========================

ROUTER_IP = "192.168.0.1"
INTERVAL  = 1



"""
3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 7c:2a:31:eb:1f:63 brd ff:ff:ff:ff:ff:ff
    inet 192.168.0.198/24 brd 192.168.0.255 scope global dynamic noprefixroute wlan0
       valid_lft 6883sec preferred_lft 6883sec
    inet6 fe80::47fc:2d39:b7fc:7b06/64 scope link noprefixroute 
       valid_lft forever preferred_lft forever


"""




class Crash_Monitor():
    """This will ping the router and alert when it stops responding"""


    # CLASS VARS
    crash_count  = 0
    online       = True


    @classmethod
    def _ping(cls):
        """Send a single ping and return (alive, latency_ms)"""

        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", ROUTER_IP],
            capture_output=True, text=True
        )

        latency = None
        if result.returncode == 0:
            for part in result.stdout.split():
                if part.startswith("time="):
                    try: latency = float(part.split("=")[1])
                    except: pass

        return result.returncode == 0, latency


    @classmethod
    def main(cls):
        """This will start the ping loop"""

        panel = Panel(
            renderable=f"[bold green]Monitoring:[/bold green] {ROUTER_IP}   [bold green]Interval:[/bold green] {INTERVAL}s",
            title="[bold red]NSM Crash Monitor",
            border_style="bold yellow",
            expand=False
        )

        console.print(panel)
        console.print(f"\n[bold yellow][*] Starting ping loop → {ROUTER_IP}\n")

        while True:

            try:

                alive, latency = cls._ping()
                ts             = datetime.now().strftime("%H:%M:%S")
                lat_str        = f"{latency:.2f}ms" if latency is not None else "N/A"

                if alive:
                    cls.online = True
                    console.print(f"[bold green][+] {ts}  →  Router online  -  [bold yellow]{lat_str}")

                else:
                    cls.online       = False
                    cls.crash_count += 1
                    console.print(f"\n[bold red][!!!] {ts}  →  ROUTER NOT RESPONDING  —  crash #{cls.crash_count}\n")

                time.sleep(INTERVAL)

            except KeyboardInterrupt: console.print("\n[bold red][-] Monitor stopped."); break
            except Exception as e:    console.print(f"[bold red][!] Error: {e}")




if __name__ == "__main__": Crash_Monitor.main()
