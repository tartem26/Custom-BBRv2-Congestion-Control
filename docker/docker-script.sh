#!/bin/bash
chmod +x training_profile.sh
./training_profile.sh &

echo " ========== Stop and Wait ========== "
python receiver.py &
python sender_stop_and_wait.py

echo " ========== Fixed Sliding Window ========== "
python receiver.py &
python sender_fixed_sliding_window.py

echo " ========== TCP Tahoe ========== "
python receiver.py &
python sender_tahoe.py

echo " ========== TCP Reno ========== "
python receiver.py &
python sender_reno.py

echo " ========== Custom Protocol ========== "
python receiver.py &
python sender_custom.py
