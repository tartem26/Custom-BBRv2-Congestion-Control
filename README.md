# Custom-BBRv2-Congestion-Control
A custom implementation of BBRv2/Tahoe–Reno hybrid UDP congestion control sender/receiver with adaptive pacing and window control using a four-state Mealy-type FSM. The algorithm utilizes STARTUP, DRAIN, PROBE_BW, and PROBE_RTT states, with bandwidth sampling, minRTT tracking, and dynamic updates to pacing_rate and cwnd/ssthresh.
