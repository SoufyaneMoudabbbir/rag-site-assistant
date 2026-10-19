#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu server (tested on Oracle Cloud Ampere A1, Ubuntu 24.04).
# Installs Docker, opens ports 80/443, enables automatic security updates and adds swap.
set -euo pipefail

sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git unattended-upgrades iptables-persistent

# Docker from Docker's official repository
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi
sudo systemctl enable --now docker

# Oracle's Ubuntu images end the INPUT chain with a REJECT rule that blocks everything
# except SSH: open HTTP and HTTPS just before it.
reject_line=$(sudo iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')
for port in 443 80; do
  sudo iptables -C INPUT -m state --state NEW -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT "${reject_line:-1}" -m state --state NEW -p tcp --dport "$port" -j ACCEPT
done
sudo netfilter-persistent save

# Automatic security updates
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

# 2 GB swap: headroom for Docker builds on a small server
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi

echo "Server ready."
