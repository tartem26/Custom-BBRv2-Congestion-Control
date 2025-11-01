import socket
from datetime import datetime
import time

# total packet size
PACKET_SIZE = 1024
# bytes reserved for sequence id
SEQ_ID_SIZE = 4
# bytes available for message
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

LARGE_FILE_DATA = None
PER_PACKET_DELAY = {}
THROUGHPUT_TIMER = 0

WINDOW_SIZE = 1

def read_data_from_file(file_name):
    # read LARGE_FILE_DATA
    global LARGE_FILE_DATA
    with open(file_name, 'rb') as f:
        LARGE_FILE_DATA = f.read()

# Stop-and-wait congestion control protocol
def stop_and_wait_send(udp_socket, message, address):
    global LARGE_FILE_DATA
    global PER_PACKET_DELAY

    while True:
        try:
            # wait for ack
            ack, _ = udp_socket.recvfrom(PACKET_SIZE)
            
            sent_id = int.from_bytes(message[:SEQ_ID_SIZE], byteorder='big')
            # extract ack id
            ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big')

            if ack_id == (sent_id + len(message) - SEQ_ID_SIZE):
                PER_PACKET_DELAY[sent_id][1] = time.time()
                return True
            else:
                return False
        except socket.timeout:
            # no ack received
            return False

def fixed_sliding_window_send(udp_socket, messages, address, acks):
    global PER_PACKET_DELAY

    # wait for acknowledgement
    while True:
        try:
            # wait for ack
            ack, _ = udp_socket.recvfrom(PACKET_SIZE)
            
            # extract ack id
            ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big')
            # print(ack_id, ack[SEQ_ID_SIZE:])

            # calculate the 
            ack_id_prev = ack_id - MESSAGE_SIZE

            if ack_id_prev in acks:
                acks[ack_id_prev] = True
                if ack_id_prev >= 0:
                    PER_PACKET_DELAY[ack_id_prev][1] = time.time()
            else:
                max_acks_key = max(acks.keys())

                # search for length of the last message
                for sid, message in messages:
                    if sid == max_acks_key:
                        ack_id_prev = ack_id - len(message) + SEQ_ID_SIZE
                        acks[ack_id_prev] = True
                        if ack_id_prev >= 0:
                            PER_PACKET_DELAY[ack_id_prev][1] = time.time()

            # all acks received, move on
            if all(acks.values()):
                return True
        except socket.timeout:
            # no ack received, resend unacked messages
            for sid, message in messages:
                if not acks[sid]:
                    udp_socket.sendto(message, address)


def tcp_tahoe(udp_socket, messages, receiver_addr, acks, ssthresh):
    # wait for acknowledgement
    global WINDOW_SIZE
    linear = False
    dup_acks = []
    counts = []

    # check if we are in congestion avoidance phase
    if WINDOW_SIZE >= ssthresh:
        linear = True

    while True:
        ack, _ = udp_socket.recvfrom(PACKET_SIZE)
        dup_acks.append(ack)

        # extract ack id
        ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big')
        print(ack_id, ack[SEQ_ID_SIZE:])
        acks[ack_id] = True

        # if TIMEOUT
        if socket.timeout:
            WINDOW_SIZE = 1
            ssthresh = WINDOW_SIZE / 2  # ssthresh reduced

            print(f"Packet {ack} lost!")
            print(f"Timeout! New ssthresh={ssthresh}, cwnd={WINDOW_SIZE}")
            return False

        # if TRIPLE DUP ACK
        for acknowledgment in dup_acks:
            if acknowledgment in dup_acks:
                counts[acknowledgment] += 1
            else:
                counts[acknowledgment] = 1
            
            # Check if the count reaches 4
            if counts[acknowledgment] == 4:
                # Triple duplicate ACK
                WINDOW_SIZE = 1
                ssthresh = WINDOW_SIZE / 2  # ssthresh reduced
                counts.clear()

                print(f"Packet {acknowledgment} was duplicated!")
                print(f"Timeout! New ssthresh={ssthresh}, cwnd={WINDOW_SIZE}")
                return False

        # if ALL RECEIVED
        if all(acks.values()):
            print("All ACK(s) received")
            if linear:
                WINDOW_SIZE = WINDOW_SIZE + 1
            else:
                WINDOW_SIZE = WINDOW_SIZE * 2
            return True


def tcp_reno(udp_socket, messages, receiver_addr, acks, ssthresh):
    # wait for acknowledgement
    global WINDOW_SIZE
    linear = False
    dup_acks = []
    counts = []

    # check if we are in congestion avoidance phase
    if WINDOW_SIZE >= ssthresh:
        linear = True

    while True:
        ack, _ = udp_socket.recvfrom(PACKET_SIZE)
        dup_acks.append(ack)

        # extract ack id
        ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big')
        print(ack_id, ack[SEQ_ID_SIZE:])
        acks[ack_id] = True

        # if TIMEOUT
        if socket.timeout:
            WINDOW_SIZE = 1
            ssthresh = WINDOW_SIZE / 2  # ssthresh reduced

            print(f"Packet {ack} lost!")
            print(f"Timeout! New ssthresh={ssthresh}, cwnd={WINDOW_SIZE}")
            return False

        # if TRIPLE DUP ACK
        for acknowledgment in dup_acks:
            if acknowledgment in dup_acks:
                counts[acknowledgment] += 1
            else:
                counts[acknowledgment] = 1
            
            # Check if the count reaches 4
            if counts[acknowledgment] == 4:
                # Triple duplicate ACK
                WINDOW_SIZE = WINDOW_SIZE / 2
                ssthresh = WINDOW_SIZE / 2  # ssthresh reduced
                counts.clear()

                print(f"Packet {acknowledgment} was duplicated!")
                print(f"Timeout! New ssthresh={ssthresh}, cwnd={WINDOW_SIZE}")
                return False

        # if ALL RECEIVED
        if all(acks.values()):
            print("All ACK(s) received")
            if linear:
                WINDOW_SIZE = WINDOW_SIZE + 1
            else:
                WINDOW_SIZE = WINDOW_SIZE * 2
            return True


def send_data(congestion_control_protocol, window_size):
    global LARGE_FILE_DATA
    global PER_PACKET_DELAY
    global THROUGHPUT_TIMER

    ssthresh = 64

    global WINDOW_SIZE
    WINDOW_SIZE = window_size

    # create a udp socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:

        # bind the socket to a OS port
        udp_socket.bind(("0.0.0.0", 5000))
        udp_socket.settimeout(1)

        throughput_timer_start = time.time()

        reciever_address = ('localhost', 5001)
        
        # start sending LARGE_FILE_DATA from 0th sequence
        seq_id = 0
        while seq_id < len(LARGE_FILE_DATA):
            # print(seq_id, len(LARGE_FILE_DATA))

            # create messages
            messages = []
            acks = {}
            seq_id_tmp = seq_id
            curret_message_size = MESSAGE_SIZE
            # Send all the packets in the window
            for i in range(WINDOW_SIZE):
                print(f"Window Size = {WINDOW_SIZE}")
                # construct messages
                # sequence id of length SEQ_ID_SIZE + message of remaining PACKET_SIZE - SEQ_ID_SIZE bytes
                
                rest_of_file = len(LARGE_FILE_DATA) - seq_id_tmp
                the_last_part = False
                if curret_message_size > rest_of_file:
                    #  calculate sise of the last part
                    curret_message_size = rest_of_file
                    the_last_part = True
                
                message = int.to_bytes(seq_id_tmp, SEQ_ID_SIZE, byteorder='big', signed=True) + LARGE_FILE_DATA[seq_id_tmp : seq_id_tmp + curret_message_size]
                messages.append((seq_id_tmp, message))
                acks[seq_id_tmp] = False
                # move seq_id tmp pointer ahead
                seq_id_tmp += curret_message_size

                if the_last_part == True:
                    break

            # send messages
            for _, message in messages:
                udp_socket.sendto(message, reciever_address)
                sent_id = int.from_bytes(message[:SEQ_ID_SIZE], byteorder='big')
                PER_PACKET_DELAY[sent_id] = [time.time(), None]
            
            if congestion_control_protocol == 'stop_and_wait_send':
                ack_result = all(stop_and_wait_send(udp_socket, message, reciever_address) for _, message in messages)
            elif congestion_control_protocol == 'fixed_sliding_window_send':
                ack_result = fixed_sliding_window_send(udp_socket, messages, reciever_address, acks)
            elif congestion_control_protocol == 'tcp_tahoe':
                ack_result = tcp_tahoe(udp_socket, messages, reciever_address, acks, ssthresh)
            elif congestion_control_protocol == 'tcp_reno':
                ack_result = tcp_reno(udp_socket, messages, reciever_address, acks, ssthresh)

            if ack_result == True:
                # move sequence id forward
                seq_id += curret_message_size + (MESSAGE_SIZE * (WINDOW_SIZE - 1))
            
        # send final closing message
        message = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + str.encode('==FINACK==')
        udp_socket.sendto(message, reciever_address)
            
        THROUGHPUT_TIMER = time.time() - throughput_timer_start

def print_per_packet_delay_statistics():
    global PER_PACKET_DELAY

    sum_delay_time = 0
    prev_delay_time = 0
    current_delay_time = 0
    sum_jitter_time = 0
    for packet_delay in PER_PACKET_DELAY:
        current_delay_time = PER_PACKET_DELAY[packet_delay][1] - PER_PACKET_DELAY[packet_delay][0]
        sum_delay_time += current_delay_time

        if packet_delay != 0:
            sum_jitter_time += abs(prev_delay_time - current_delay_time)

        prev_delay_time = current_delay_time

    agv_delay = sum_delay_time/len(PER_PACKET_DELAY)
    avg_jitter = sum_jitter_time/(len(PER_PACKET_DELAY) - 1)

    Metric = 0.2 *(THROUGHPUT_TIMER/2000) + 0.1/avg_jitter + 0.8/agv_delay

    print('Throughput (sec) = ', THROUGHPUT_TIMER)
    print("Avg per packet delay (sec) = ", str(agv_delay))
    print("Jitter, (sec) = ", str(avg_jitter))
    print("Metric = ", Metric)

print('Sender running')

read_data_from_file('./file.mp3')

# send_data('stop_and_wait_send', 1)
# send_data('fixed_sliding_window_send', 100)

send_data('tcp_tahoe', 1)

# send_data('tcp_reno', 1)

print('Transmission finished')

print_per_packet_delay_statistics()
