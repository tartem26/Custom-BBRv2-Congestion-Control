# Custom-BBRv2-Congestion-Control
A custom implementation of BBRv2/Tahoe–Reno hybrid UDP congestion control sender/receiver with adaptive pacing and window control using a four-state Mealy-type FSM. The algorithm utilizes STARTUP, DRAIN, PROBE_BW, and PROBE_RTT states, with bandwidth sampling, minRTT tracking, and dynamic updates to pacing_rate and cwnd/ssthresh.

## Features
- **Packet I/O over UDP** with fixed packet/sequence framing and timeouts.
- **Memory-mapped file reader** for efficient chunking.
- **Metrics:** throughput, avg delay, jitter, and a composite performance metric with a ready-to-print summary.

## Algorithms Implemented
- **Stop-and-Wait** and **Fixed Sliding Window** senders.
- **TCP Tahoe/Reno-style** behavior (slow start, congestion avoidance, timeout & triple-dup-ACK handling).
- **Custom variant** (sender_type 'C') that, on triple dup-ACK, sets `cwnd = ssthresh + 3` before fast retransmit.

## Repository Layout
- `receiver.py`: UDP receiver that reassembles data and ACKs next expected byte; writes output after completion.
- `utils.py`: Packet format, UDP socket wrapper, FileReader, metrics, and TahoeRenoSender.
- `sender_stop_and_wait.py`, `sender_fixed_sliding_window.py`: Simple senders.
- `sender_tahoe.py`, `sender_reno.py`, `sender_custom.py`: Thin launchers for TahoeRenoSender (types 'T', 'R', 'C').
- `tahoe_reno_sender.py`, `improved_tahoe_reno_sender.py`, `sender.py` – Alternate/earlier implementations of Tahoe/Reno behavior and helpers.

## Quickstart
1. Start the receiver in one shell:
   ```python
   python receiver.py
   ```
   > **Defaults:** binds `0.0.0.0:5001` and prints ACKs/events.
2. Send a file (choose a sender in another shell):
   - **Tahoe:** `python sender_tahoe.py`
   - **Reno:** `python sender_reno.py`
   - **Custom (Tahoe/Reno):** `python sender_custom.py`
> Each launcher uses `TahoeRenoSender(...).send('./file.mp3', 'localhost', 5001)`.
> **Note:** Stop-and-Wait / Fixed Sliding Window variants live in `utils.py` as separate classes.

## How It Works (High-Level)
- **Framing:** `SEQ_ID_SIZE=4`, `PACKET_SIZE=1024`, `payload = MESSAGE_SIZE`. Sender prepends `seq_id` to each UDP payload.
- **ACK:** Receiver tracks next expected byte (`EXPECTED_SEQ_ID` logic) and ACKs cumulative progress; issues FIN/ACK on completion.
- **Congestion Control:** `TahoeRenoSender` grows `cwnd` exponentially below `ssthresh`, linearly above; handles dup-ACKs and timeouts per Tahoe/Reno/custom rules, then fast-retransmits.

## Measuring Performance
After a run, metrics print to stdout: Throughput (bytes/s), Average Delay, Average Jitter, and a composite metric.

