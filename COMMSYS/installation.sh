#!/bin/bash

echo "Installing required Python libraries: RPi.GPIO and spidev"

# Update package lists
sudo apt update

# Install RPi.GPIO (usually pre-installed, but safe to include)
sudo apt install -y python3-rpi.gpio

# Install spidev for SPI communication
sudo pip3 install spidev

echo "Installation complete. Ensure SPI is enabled in raspi-config."
echo "You may need to reboot after enabling SPI."
