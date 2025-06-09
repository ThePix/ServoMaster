#!/bin/bash
echo "Shutting down 3" >> /home/f2andy/servo_log.txt
date >> /home/f2andy/servo_log.txt
sleep 2
sudo shutdown -h now
