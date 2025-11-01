# ======================================================================
#                   utils.py
# ======================================================================

import os
import socket
import time
import mmap
import logging

logger = logging.getLogger(__name__)

MAX_DUP_ACKS = 3
TIMEOUT = 1.0  # Timeout for retransmission in seconds

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

class UdpTcpSocket:
    def __init__(self, host, port, timeout):
        self.address = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)

    def create_packet(self, seq_id, data):
        return seq_id.to_bytes(SEQ_ID_SIZE, signed=True, byteorder='big') + data

    def send_packet(self, packet):
        self.socket.sendto(packet, self.address)

    def receive_packet(self):
        packet, _address = self.socket.recvfrom(PACKET_SIZE)
        seq_id = int.from_bytes(packet[:SEQ_ID_SIZE], signed=True, byteorder='big')
        data = packet[SEQ_ID_SIZE:]

        return seq_id, data

    def close(self):
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class FileReader:
    def __init__(self, path) -> None:
        self.path = path
        self.file_size = os.path.getsize(self.path)
        with open(path, 'rb') as f:
            self.mmap_obj = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    def read(self, start, length):
        end = start + length
        if end > self.file_size:
            length = self.file_size - start
        self.mmap_obj.seek(start)
        data = self.mmap_obj.read(length)
        return data, length

    def __del__(self):
        self.mmap_obj.close()
    

class PerformanceMetrics:
    def __init__(self):
        self.start_time = 0
        self.end_time = 0
        self.packet_delay_tracker = {}
        self.total_data_sent = 0
    
    def start(self):
        self.start_time = time.time()

    def end(self):
        self.end_time = time.time()

    def start_packet(self, seq_id, packet):
        if seq_id in self.packet_delay_tracker:
            return
        self.packet_delay_tracker[seq_id] = (time.time(), -1)
        self.total_data_sent += len(packet)

    def end_packet(self, seq_id):
        logger.debug(f"Packet {seq_id} received")
        self.packet_delay_tracker[seq_id] = (self.packet_delay_tracker[seq_id][0], time.time())

    def calculate_throughput(self):
        return self.total_data_sent / (self.end_time - self.start_time)

    def calculate_metrics(self):
        """Calculate throughput, average delay, jitter, and metric."""
        
        throughput = self.calculate_throughput()

        sorted_packets = sorted(self.packet_delay_tracker.items(), key=lambda x: x[0])

        # ensure there are not -1 for awks that were skipped by replacing them 
        # with the end time with the end time from the next packet
        last_end_time = self.end_time
        for i in reversed(range(len(sorted_packets) - 1)):
            if sorted_packets[i][1][1] == -1:
                sorted_packets[i] = (sorted_packets[i][0], (sorted_packets[i][1][0], last_end_time))
            else:
                last_end_time = sorted_packets[i][1][1]


        for seq_id, (start, end) in sorted_packets:
            if end == -1:
                logger.warning(f"Packet {seq_id} was not received")

        packet_delays = [end - start for _, (start, end) in sorted_packets if end != -1]
        # Average per-packet delay
        avg_delay = sum(packet_delays) / len(packet_delays)

        # Jitter calculation
        jitters = [abs(packet_delays[i + 1] - packet_delays[i]) for i in range(len(packet_delays) - 1)]
        avg_jitter = sum(jitters) / len(jitters) if jitters else 0

        # Metric calculation
        part_1 = 0.2 * (throughput / 2000)
        part_2 = 0.1 / avg_jitter
        part_3 = 0.8 / avg_delay
        metric = part_1 + part_2 + part_3

        return throughput, avg_delay, avg_jitter, metric
    
    def print_metrics(self):
        throughput, avg_delay, avg_jitter, metric = self.calculate_metrics()
        
        print(f"Throughput: {throughput:.2f} bytes/sec")
        print(f"Average Delay: {avg_delay:.6f} seconds")
        print(f"Average Jitter: {avg_jitter:.6f} seconds")
        print(f"Performance Metric: {metric:.6f}")

class TahoeRenoSender:
    def __init__(self, sender_type) -> None:
        self.sender_type = sender_type

    def send(self, file_path, server_address, server_port):
        # TCP Tahoe/Reno parameters
        cwnd = 1  # Congestion window size in packets
        ssthresh = 64  # Slow start threshold
        dup_ack_count = 0

        reader = FileReader(file_path)
        base = 0
        next_seq = 0
        
        pref = PerformanceMetrics()
        pref.start()

        with UdpTcpSocket(server_address, server_port, TIMEOUT) as soc:
            while base < reader.file_size:
                while next_seq < base + cwnd * MESSAGE_SIZE and next_seq < reader.file_size:
                    seq_id = next_seq
                    message_bytes, message_size = reader.read(seq_id, MESSAGE_SIZE)
                    next_seq += message_size
                    packet = soc.create_packet(seq_id, message_bytes)
                    pref.start_packet(next_seq, packet)
                    soc.send_packet(packet)
                    logger.info(f"Sent packet {seq_id}")
                try:
                    ack_id, _awk_data = soc.receive_packet()
                    logger.info(f"Received ACK for {ack_id}")

                    if ack_id > base:
                        base = ack_id
                        dup_ack_count = 0

                        # Adjust congestion window
                        if cwnd < ssthresh:
                            cwnd *= 2
                        else:
                            cwnd += 1

                    elif ack_id == base:
                        dup_ack_count += 1
                        if dup_ack_count >= MAX_DUP_ACKS:
                            logger.warning("Triple duplicate ACK, performing fast retransmit")
                            ssthresh = max(cwnd // 2, 1)
                            if self.sender_type == 'T':
                                cwnd = 1
                            elif self.sender_type == 'R':
                                cwnd = ssthresh
                            elif self.sender_type == 'C':
                                # Custom
                                cwnd = ssthresh + 3
                            else:
                                logger.fatal("TahoeRenoSender incorrect sender_type!")
                            
                            message_bytes, _message_size = reader.read(base, MESSAGE_SIZE)
                            packet = soc.create_packet(base, message_bytes)
                            soc.send_packet(packet)
                            logger.info(f"Retransmitted packet {base}")

                    # Stop the timer for this packet
                    pref.end_packet(ack_id)

                except socket.timeout:
                    logger.warning("Timeout occurred, reducing window size")
                    ssthresh = max(cwnd // 2, 1)
                    cwnd = 1
                    next_seq = base

            finack_packet = soc.create_packet(-1, b'==FINACK==')
            soc.send_packet(finack_packet)
            logger.info("File transmission complete")

        pref.end()
        pref.print_metrics()

class StopAndWaitSender:
    def __init__(self) -> None:
        pass

    def send(self, file_path, server_address, server_port):
        reader = FileReader(file_path)
        next_seq = 0
        
        pref = PerformanceMetrics()
        pref.start()

        with UdpTcpSocket(server_address, server_port, TIMEOUT) as soc:
            while next_seq < reader.file_size:
                seq_id = next_seq
                message_bytes, message_size = reader.read(seq_id, MESSAGE_SIZE)
                next_seq += message_size
                packet = soc.create_packet(seq_id, message_bytes)
                pref.start_packet(next_seq, packet)
                soc.send_packet(packet)
                logger.info(f"Sent packet {seq_id}")

                try:
                    ack_id, _awk_data = soc.receive_packet()
                    logger.info(f"Received ACK for {ack_id}")

                    if ack_id <= seq_id:
                        next_seq = seq_id
                        logger.info(f"Retransmitted packet {seq_id}")
                    else:
                        # Stop the timer for this packet
                        pref.end_packet(ack_id)

                except socket.timeout:
                    logger.warning("Timeout occurred, resend")
                    next_seq = seq_id

            finack_packet = soc.create_packet(-1, b'==FINACK==')
            soc.send_packet(finack_packet)
            logger.info("File transmission complete")

        pref.end()
        pref.print_metrics()

class FixedSlidingWindowSender:
    def __init__(self, window_size) -> None:
        self.window_size = window_size

    def send(self, file_path, server_address, server_port):
        reader = FileReader(file_path)
        base = 0
        next_seq = 0
        
        pref = PerformanceMetrics()
        pref.start()

        with UdpTcpSocket(server_address, server_port, TIMEOUT) as soc:
            while base < reader.file_size:
                messages = []
                acks = {}
                while next_seq < base + self.window_size * MESSAGE_SIZE and next_seq < reader.file_size:
                    seq_id = next_seq
                    message_bytes, message_size = reader.read(seq_id, MESSAGE_SIZE)
                    next_seq += message_size
                    packet = soc.create_packet(seq_id, message_bytes)
                    
                    messages.append((next_seq, packet))
                    acks[next_seq] = False

                    pref.start_packet(next_seq, packet)
                    soc.send_packet(packet)
                    logger.info(f"Sent packet {seq_id}")

                # wait for acknowledgement
                while True:
                    try:
                        ack_id, _awk_data = soc.receive_packet()
                        logger.info(f"Received ACK for {ack_id}")

                        if ack_id in acks:
                            # Stop the timer for this packet
                            pref.end_packet(ack_id)
                            acks[ack_id] = True

                        # all acks received, move on
                        if all(acks.values()):
                            base = next_seq
                            break

                    except socket.timeout:
                        logger.warning("Timeout occurred, resend unacked messages")
                        for sid, packet in messages:
                            if not acks[sid]:
                                soc.send_packet(packet)

            finack_packet = soc.create_packet(-1, b'==FINACK==')
            soc.send_packet(finack_packet)
            logger.info("File transmission complete")

        pref.end()
        pref.print_metrics()

# ======================================================================
#                  END of utils.py
# ======================================================================
