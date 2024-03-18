#!/usr/bin/env python

import os
import math
import random
import socket
import struct
import sys
from collections import OrderedDict
from collections.abc import Generator
from processify import processify
from typing import Tuple

STRING_ENCODING = 'utf-8'

class Crawler:
    def __init__(self, files: list[str]) -> None:
        # Environment variables
        self.force_metadata = os.getenv("CRWL_METADATA")
        self.force_mode = str(os.getenv("CRWL_MODE", "block"))
        try:
            self.force_seqn = int(os.getenv("CRWL_SEQN", "0"))
        except ValueError:
            self.force_seqn = 0
        self.force_out_of_order = os.getenv("CRWL_FORCE_OUT_OF_ORDER")
        self.force_errors = os.getenv("CRWL_FORCE_ERROR")
        self.force_duplicate = os.getenv("CRWL_FORCE_DUPLICATE")
        self.no_hamming = os.getenv("CRWL_NO_HAMMING")
        self.no_rle = os.getenv("CRWL_NO_RLE")
        try:
            self.rx_timeout = int(os.getenv("CRWL_RX_TIMEOUT", "5"))
        except ValueError:
            self.rx_timeout = 5
        self.debug = os.getenv("CRWL_DEBUG")

        # Crawler data
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(self.rx_timeout)
        self.id = random.randint(1, 0xFFFF)
        self.files = files
        self.seqn = self.force_seqn
        self.upload_id = 0

        # Hamming code variables
        self.raw_chunk = 0
        self.encoded_chunk = 0

        # Track upload progress
        self.current_chunk = 0
        self.chunks_in_file = 0

        # Track packets sent
        self.current_packet = ""
        self.packet_queue : OrderedDict[int | str, bytes] = OrderedDict()
        self.out_of_order_packets : list[bytearray | bytes] = []
        self.adding_ooo_packets = True

        # Constants
        self.is_little_endian = sys.byteorder == 'little'
        self.bits_per_block = 256
        self.parity_bits_per_block = int(math.log2(self.bits_per_block)) + 1
        self.data_bits_per_block = self.bits_per_block - self.parity_bits_per_block
        self.print_debug(f"Using Extended Hamming({self.bits_per_block - 1}, {self.data_bits_per_block})")

        self.print_debug(f"Will upload {len(self.files)} files")

    def run(self) -> None:
        if self.force_duplicate:
            self.files.insert(0, self.files[0])
        for file in self.files:
            self.upload_file(file)
        self.sock.close()

    def upload_file(self, file: str) -> None:
        self.print_debug(f"Uploading {file}")
        self.send_upld(file)
        if self.force_mode != "block" or self.force_metadata:
            self.send_mode(self.force_mode)
        if self.force_seqn != 0 or self.force_metadata:
            self.send_seqn(self.force_seqn)
        with open(file, "rb") as fd:
            file_size = os.path.getsize(file)
            chunk_size = 498
            self.chunks_in_file = math.ceil(file_size / chunk_size)
            for i in range(0, file_size, chunk_size):
                self.current_chunk = i
                data = fd.read(chunk_size)
                self.send_data(data)
        self.adding_ooo_packets = False
        if self.force_out_of_order:
            for data in self.out_of_order_packets:
                self.send_recv(data)
        self.current_chunk += 1
        self.send_data(b'')

    # Packet methods

    def send_upld(self, file: str) -> None:
        self.current_packet = "UPLD"
        data = self.get_header(self.current_packet, len(file))
        data += file.encode(STRING_ENCODING)
        response = bytearray(b'')
        expected = b"UPLOADING"
        while not response.startswith(expected):
            #response = bytearray(self.send_recv(data))
            response = bytearray(b"UPLOADING\x12\x34")
        _, id = struct.unpack(f"!{len(expected)}sH", response)
        self.upload_id = id

    def send_mode(self, mode: str) -> None:
        self.current_packet = "MODE"
        data = self.get_header(self.current_packet, len(mode))
        data += mode.encode(STRING_ENCODING)
        response = bytearray(b'')
        while response != b"METADATAMODE":
            _ = self.send_recv(data)

    def send_seqn(self, sequence: int) -> None:
        self.current_packet = "SEQN"
        format = "!H"
        data = self.get_header(self.current_packet, struct.calcsize(format))
        data += struct.pack(format, sequence)
        response = bytearray(b'')
        while response != b"METADATASEQN":
            _ = self.send_recv(data)

    def send_data(self, chunk: bytes) -> None:
        self.current_packet = str(self.seqn)
        data = self.get_header("DATA", len(chunk))
        data += struct.pack("!HH", self.upload_id, self.seqn)
        self.seqn += 1
        data += chunk
        self.send_recv(data)

    # Network-related methods

    def send_recv(self, data: bytes) -> bytes:
        arr = bytearray(data)
        if len(arr) & 1:
            arr += "\x00".encode(STRING_ENCODING)
        self.send(arr)
        response = self.recv()
        if self.payload_starts_with(response, b"IAMERR"):
            self.handle_error(response)
        elif self.payload_starts_with(response, b"LOSS"):
            self.handle_loss(response)
        return response

    def send(self, data: bytes) -> None:
        if not self.no_hamming:
            to_send = self.hamming_encode(data)
        else:
            to_send = int.from_bytes(data, 'big')
        length = to_send.bit_length() // 8 + 1
        if not self.no_rle:
            to_send_bytes = int.to_bytes(to_send, length=length, byteorder='big')
            encoded_bytes = self.run_length_encode(to_send_bytes)
            to_send = int.from_bytes(encoded_bytes, 'big')
            length = to_send.bit_length() // 8 + 1

        is_out_of_order = False
        if self.adding_ooo_packets and self.force_out_of_order and self.current_packet.isnumeric():
            is_out_of_order = random.choices([False, True], weights=[100, 1])[0]
            if is_out_of_order:
                self.out_of_order_packets.append(data)

        if not is_out_of_order:
            msg = int.to_bytes(to_send, length, 'big')
            #self.sock.sendto(msg, ("localhost", 7331))
        self.packet_queue[self.current_packet] = data

    def recv(self) -> bytes:
        return b''
        try:
            resp, _ = self.sock.recvfrom(1024)
            self.print_debug(f"Response: {resp.decode(STRING_ENCODING)}")
        except TimeoutError:
            self.print_debug(f"Timed out while waiting for server response")
            resp = b''
        return resp

    def get_header(self, command: str, payload_size: int) -> bytes:
        header = struct.pack("!HHH", 0xC505, payload_size + 6, self.id)
        header += command.encode(STRING_ENCODING)
        return header

    def handle_loss(self, response: bytes) -> None:
        header_fmt = "!4sH"
        header_length = struct.calcsize(header_fmt)
        #_, length = struct.unpack(header_fmt, response[0:header_length])
        packet_numbers = response[header_length:]
        packets_lost = [x[0] for x in struct.iter_unpack("!H", packet_numbers)]
        for seqn in packets_lost:
            self.current_packet = seqn
            response = self.send_recv(self.packet_queue[seqn])
            loss_packets_lost = []
            if self.payload_starts_with(response, b"LOSS"):
                loss_packets_lost.append(seqn)
        if len(loss_packets_lost) > 0:
            self.handle_loss(response)

    def handle_error(self, response: bytes) -> None:
        header_fmt = "!6sH"
        header_length = struct.calcsize(header_fmt)
        _, length = struct.unpack(header_fmt, response[0:header_length])
        message = struct.unpack(f"{length - header_length}s", response[header_length:])
        self.print_debug(f"Received error: {message}")

    # Hamming code methods

    def hamming_encode(self, message: bytes | bytearray) -> int:
        self.raw_chunk = int.from_bytes(message, 'big')
        self.prepare_chunk()
        self.compute_parity()
        if self.force_errors:
            error_count = random.choices([2, 1, 0], weights=[5, 20, 50])[0]
            for _ in range(error_count):
                # There's a chance that this reflips the same bit... Oh well
                bit = random.randint(1, self.bits_per_block - 1)
                self.encoded_chunk = self.flip_bit(self.encoded_chunk, bit)
        return self.encoded_chunk

    def prepare_chunk(self) -> int:
        self.encoded_chunk = 0
        bits_used = 0
        for i in range(self.bits_per_block):
            if not self.is_parity_bit(i):
                bit_value = self.get_bit(self.raw_chunk, bits_used)
                self.encoded_chunk = self.set_bit(self.encoded_chunk, i, bit_value)
                bits_used += 1
        assert(bits_used == self.data_bits_per_block)
        return self.encoded_chunk

    def compute_parity(self) -> int:
        from functools import reduce
        if self.encoded_chunk == 0:
            return 0
        bits = [int(bit) for bit in self.get_bitstring(self.encoded_chunk)]
        parity = reduce(lambda x, y: x ^ y, self.get_on_bits(bits, self.bits_per_block))
        parity_bits = list(self.get_bitstring(parity, self.parity_bits_per_block - 1))
        parity_bits = parity_bits[::-1]
        for i, parity_bit in enumerate(parity_bits):
            parity_index = 1 << i
            self.encoded_chunk = self.set_bit(self.encoded_chunk, parity_index, int(parity_bit))
        bits = [int(bit) for bit in self.get_bitstring(self.encoded_chunk)]
        parity = len(self.get_on_bits(bits, self.bits_per_block))
        self.encoded_chunk = self.set_bit(self.encoded_chunk, 0, 1 if parity & 1 else 0)
        assert(reduce(lambda x, y: x ^ y, self.get_on_bits(bits, self.bits_per_block)) == 0)
        return self.encoded_chunk

    def is_parity_bit(self, pos: int) -> bool:
        return (pos & (pos - 1)) == 0

    def get_bit(self, n: int, bit_index: int) -> int:
        return (n >> bit_index) & 1

    def set_bit(self, n: int, bit_index: int, value: int) -> int:
        mask = 1 << bit_index
        n &= ~mask
        if value:
            n |= mask
        return n

    def flip_bit(self, n :int, bit_index: int) -> int:
        val = self.get_bit(n, bit_index)
        return self.set_bit(n, bit_index, 0 if val else 1)

    def get_on_bits(self, bits: list[int], bit_length: int) -> list[int]:
        return [bit_length - i - 1 for i, bit in enumerate(bits) if bit]

    def get_bitstring(self, block: int, bit_length: int = -1) -> str:
        if bit_length == -1:
            bit_length = self.bits_per_block
        return format(block, f'0{bit_length}b')

    # Run length encoding methods

    def run_length_encode(self, data: bytes | bytearray) -> bytes:
        def rle(data: bytes | bytearray) -> list[Tuple[int, int]]:
            from itertools import groupby
            return list((x, sum(1 for _ in y)) for x, y in groupby(data))
        encoded_data = rle(data)
        ret = b''
        for ch, count in encoded_data:
            ret += str.encode(chr(ch), STRING_ENCODING)
            ret += int.to_bytes(count)
        return ret

    # Utility methods

    def host_to_network_bytes(self, block: bytes | bytearray) -> bytearray:
        arr = [x[0] for x in struct.iter_unpack('=H', block)]
        bytes = struct.pack(f"!{len(arr) * 'H'}", *arr)
        return bytearray(bytes)

    def network_to_host_bytes(self, block: bytes | bytearray) -> bytearray:
        arr = [x[0] for x in struct.iter_unpack("!H", block)]
        bytes = struct.pack(f"={len(arr) * 'H'}", *arr)
        return bytearray(bytes)

    def payload_starts_with(self, payload: bytes | bytearray, prefix: bytes | bytearray) -> bool:
        return len(payload) >= len(prefix) and payload.startswith(prefix)

    def print_block(self, b: int) -> None:
        block_str = self.get_bitstring(b)
        self.print_debug(f"{block_str}")

    def print_debug(self, s: str) -> None:
        if self.debug:
            print(f"Crawler #{self.id}: {s}")


#@processify
def invoke(files: list[str]) -> None:
    crawler = Crawler(files)
    crawler.run()

def scantree(path: str, recurse: bool) -> list[str]:
    """List the files in a given directory."""
    def do_work(path: str, recurse: bool) -> Generator[os.DirEntry, None, None]:
        """Recursively yield DirEntry objects for given directory."""
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                if recurse:
                    yield from do_work(entry.path, recurse)
            else:
                yield entry
    if not os.path.isfile(path):
        files = do_work(path, recurse)
        return [file.path for file in files]
    return [path]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="File crawler. Its behaviour can be controlled with environement variables (see os.en.md/os.fr.md).")
    parser.add_argument("--path", "-p", type=str, help="The file path to crawl. If this is a folder, it will crawl all its files.", default="/tmp")
    parser.add_argument("--recurse", action=argparse.BooleanOptionalAction, help="Recursively crawl the given path (or parent directory).")
    args = parser.parse_args()

    files = scantree(args.path, args.recurse)
    try:
        nb_crawlers = int(os.getenv("CRWL_NB_CRAWLERS", "2"))
    except (ValueError):
        nb_crawlers = 2

    files_per_crawler = int(len(files) / nb_crawlers) + 1
    file_names = '\n'.join(files)
    for i in range(0, len(files), files_per_crawler):
        crawler_files = files[i : i + files_per_crawler]
        file_names = '\n'.join(crawler_files)
        invoke(crawler_files)