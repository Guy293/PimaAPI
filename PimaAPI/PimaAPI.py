import random
import socket
from time import sleep

from .constants import (
    ARM_TYPES,
    END_BYTE,
    INDICATORS,
    START_BYTE,
    SYSTEM_STATUS,
    UDP_WAKEUP_PAYLOADS_INT,
)
from .utils import crc16_xmodem, retry


class PimaAPI:
    udp_wakeup_payloads = []
    sock = None
    system_type = None
    zones = None
    data = None
    num_of_partitions = None
    is_part = None
    system_status = None
    system_status_text = None
    panel_version = None

    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.num_of_partitions = 0

        # Convert to signed bytes
        for payload_int in UDP_WAKEUP_PAYLOADS_INT:
            payload = bytes(0)
            for i in payload_int:
                payload += i.to_bytes(1, byteorder="little", signed=True)

            self.udp_wakeup_payloads.append(payload)

        @retry(socket.timeout, attempts=4)
        def connect():
            if self.sock:
                print("Disconnecting...")
                self.disconnect()
                sleep(4)

            print("sending udp wakeup")
            self.udp_wakeup()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)

            print("connecting...")
            self.sock.connect((self.host, self.port))

            self._auth()
            print(
                f"Authenticated, system type: {self.system_type}, zones: {self.zones}"
            )

        connect()

        self.update_system_status()

        print(
            f"system status type: {self.system_status}, text: {self.system_status_text}, is_part: {self.is_part}, num_of_partitions: {self.num_of_partitions}"
        )

        self.update_panel_version()
        print(f"panel version: {self.panel_version}")

        print(
            f"system status type: {self.system_status}, text: {self.system_status_text}, is_part: {self.is_part}, num_of_partitions: {self.num_of_partitions}"
        )

        print("Disconnecting...")
        self.disconnect()

    def udp_wakeup(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        for _ in range(2):
            sock.sendto(random.choice(self.udp_wakeup_payloads), (self.host, self.port))
            sleep(0.1)

    def _send(self, indicator, data):
        body = f"{indicator}={data}".encode()
        crc = crc16_xmodem(bytes.fromhex("ff") + body)
        self.sock.send(START_BYTE + body + crc + END_BYTE)

    def _recv(self):
        data = self.sock.recv(1024)
        if data == b"":
            raise socket.timeout()
        # data = data[data.find(START_BYTE) + 1 : data.find(END_BYTE) - 3]
        data = data[1:-3]  # Remove start, CRC and end bytes (TODO Implement CRC check)
        return data.decode().split("=")

    @retry(socket.timeout, 2)
    def _auth(self):
        # TODO Check valid login
        print("Authing...")
        self._send(INDICATORS.Auth, self.password)
        # Returns system type and zones
        indicator, data = self._recv()
        assert indicator == "PR" or indicator == "PT"

        if indicator == "PR":
            self.system_type = 0
        elif indicator == "PT":
            self.system_type = 1
            self.zones = int(data[1:])

    def disconnect(self):
        try:
            self._send(INDICATORS.Disconnect, "1")
        except socket.timeout:
            pass
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def update_system_status(self):
        self._send(INDICATORS.SystemStatus, "1")
        self._handle_system_status()

    def _handle_system_status(self):
        indicator, data = self._recv()
        assert indicator == "PS"

        self.is_part = False

        is_disarmed = False
        for val in data:
            val = int(val)
            if val >= 0 and val <= 5:
                self.num_of_partitions += 1
            if val == 0:
                is_disarmed = True

        if self.num_of_partitions > 0:
            self.is_part = True

        if not self.is_part:
            _type = int(data[0])
            self.system_status = SYSTEM_STATUS(_type)
            self.system_status_text = data[1:]
        else:
            if is_disarmed:
                self.system_status = SYSTEM_STATUS.Disarm
            else:
                self.system_status = SYSTEM_STATUS.Full

            self.system_status_text = data

    def update_panel_version(self):
        self._send(INDICATORS.PanelVersion, "1")

        indicator, data = self._recv()
        assert indicator == "VR"

        self.panel_version = data

    def arm(self, arm_type: ARM_TYPES):
        self._send(INDICATORS.Arm, arm_type.value)
        # Returns system status
        self._handle_system_status()

    def disarm(self):
        self._send(INDICATORS.Disarm, "1")
        # Returns system status
        self._handle_system_status()
