# Custom BBRv2 Congestion Control
A custom implementation of a **BBRv2/Tahoe–Reno** hybrid User Datagram Protocol (UDP) congestion control sender/receiver with adaptive pacing and window control using a four-state Mealy-type FSM. The algorithm utilizes `STARTUP`, `DRAIN`, `PROBE_BW`, and `PROBE_RTT` states, with bandwidth sampling, `minRTT` tracking, and dynamic updates to `pacing_rate` and `cwnd`/`ssthresh`.

## Features
- **Packet I/O over UDP** with fixed packet/sequence framing and timeouts.
- **Memory-mapped file reader** for efficient chunking.
- **Metrics:** throughput, avg delay, jitter, and a composite performance metric with a ready-to-print summary.

## Algorithms Implemented
- **Stop-and-Wait** and **Fixed Sliding Window** senders.
- **TCP Tahoe/Reno-style** behavior (slow start, congestion avoidance, timeout & triple-dup-ACK (Acknowledgment) handling).
- **Custom variant** (sender_type 'C')
     - Four-state **Mealy FSM** (`STARTUP`/`DRAIN`/`PROBE_BW`/`PROBE_RTT`) with **bandwidth sampling** and **Minimum Round-Trip Time** `minRTT` tracking.  
  - **Rate & window coupling:** updates `pacing_rate` from bandwidth estimate and maintains `cwnd`/`ssthresh` near the Bandwidth–Delay Product (`BDP = bw_estimate × minRTT`, where `bw_estimate` is measured bottleneck bandwidth (bytes/s) from delivery rate sampling and `minRTT` is a current minimal RTT sample (s), approximating path propagation delay).  
  - On **triple dup-ACK**, sets `cwnd = ssthresh + 3` and fast-retransmits, where `cwnd` is a **Congestion Window** and `ssthresh` is a **Slow-Start Threshold**.
  - On timeout, Tahoe-style reset.

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
- **Congestion Control:**
     - **Tahoe/Reno:**
        - `TahoeRenoSender` exponential grows `cwnd` below `ssthresh`, linear above.
        - Handles dup-ACK timeout backoff/reset per Tahoe/Reno/custom rules and then fast retransmit.
     - **Custom hybrid:**
        - BBRv2-style `STARTUP` → `DRAIN` → `PROBE_BW`/`PROBE_RTT` with `pacing_rate = gain × bw_estimate`, `cwnd` near BDP (`bw_estimate × minRTT`), and periodic `minRTT` refresh.
        - Reno/Tahoe rules for loss (3 dup-ACK → `cwnd = ssthresh + 3` + fast retransmit; timeout → Tahoe reset).

## Custom Hybrid (BBRv2 + Tahoe/Reno)

### Design
Four-state, Mealy-type FSM (`STARTUP`, `DRAIN`, `PROBE_BW`, `PROBE_RTT`) with bandwidth sampling, `minRTT` tracking, and dual controls: `pacing_rate` (sender pacing) and `cwnd`/`ssthresh` (flight size).

### Key mechanics
- **Bandwidth & RTT sampling:** rolling samples from delivered bytes / RTT, where `minRTT` is maintained as a floor (periodically refreshed).
- **Rate/Window coupling:**
     - `pacing_rate = gain * bw_estimate` (state-dependent gain)
     - `BDP = bw_estimate * minRTT`
     - `cwnd = clamp(BDP * cwnd_gain, cwnd_min, cwnd_max)`
- **`STARTUP` → `DRAIN`:** exponential growth to find pipe, then drain in-flight to match `BDP`.
- **`PROBE_BW`:** paced gain cycling to test for more bandwidth and keeps `cwnd` near `BDP` with gentle probing.
- **`PROBE_RTT`:** temporarily caps `cwnd` to a small value, re-measures `minRTT`, then returns to `PROBE_BW`.
- **Loss & ACK signals (hybrid):**
     - **Triple dup-ACK (fast retransmit):**
          - Tahoe/Reno-style:
               - Sets `ssthresh = max(inflight / 2, 2 * MSS)` (where `MSS` is a **Maximum Segment Size**), fast-retransmit the missing segment, and `cwnd` ← `ssthresh` + `3 * MSS` (keeps the pipe warm).
               - Exits with an additive increase.
     - **Timeout:** Tahoe reset (`cwnd` → `1 – 2 * MSS`, `ssthresh` halved), then slow-start.
     - **Recovery bump:** modest `cwnd` bump on partial recovery ACKs (Reno flavor) to stabilize throughput.
- **Stability tooling:** thread-safe send/recv, explicit timers, and selective backoff on late/var-RTT paths.

### Why It Is Fast in Practice
- BBRv2's pacing learns the pipe quickly since Reno/Tahoe loss logic prevents standing queues from tanking latency.
- `cwnd` stays near `BDP` (keeps link full), while pacing gain cycles opportunistically find headroom without bufferbloat.

### Select the Custom Sender
```sh
python sender_custom.py         # or construct with sender type 'C'
# e.g., TahoeRenoSender('C').send(INPUT, HOST, PORT)
```

### Typical Tunables
Probe gains (↑/↓ cycle), `minRTT` refresh interval, dup-ACK threshold (3), timeout/backoff constants, and `cwnd` clamps.

### Result
Top-3 / ~250 entrants on the `5.07` MB transfer task; earned automatic A in the course and a final-exam waiver.

## Measuring Performance
After a run, metrics print to stdout: Throughput (bytes/s), Average Delay, Average Jitter, and a composite metric.

## Troubleshooting
- Use consistent MSS and buffer sizes between sender and receiver.
- If RTT variance is high, verify OS socket buffers and local emulator limits.
- For reproducible results, pin Python and dependency versions and run on the same host/OS.
