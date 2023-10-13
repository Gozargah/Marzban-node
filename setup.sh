#!/bin/bash

# Step 1: Update the system
echo "Step 1: Updating the system..."
sudo apt update
sudo apt upgrade -y

# Step 2: Clone the GitHub repository to /var/opt
echo "Step 2: Cloning the GitHub repository to /var/opt..."
cd /var/opt
git clone https://github.com/dry-stan/Marzban-node.git

# Check if the repository was cloned successfully
if [ $? -ne 0 ]; then
  echo "Failed to clone the GitHub repository."
  exit 1
fi

# Search for the Marzban-node directory across the whole system
marzban_node_dir=$(find / -type d -name "Marzban-node" 2>/dev/null)

if [ -z "$marzban_node_dir" ]; then
  echo "Marzban-node directory not found."
  exit 1
fi

# Step 3: Download pip for Python 3
echo "Step 3: Downloading and installing pip for Python 3..."
sudo apt install python3-pip -y

# Change to the Marzban-node directory
echo "Step 4: Changing to the Marzban-node directory..."
cd "$marzban_node_dir"

# Step 5: Install dependencies from requirements.txt
echo "Step 5: Installing dependencies from requirements.txt..."
pip3 install -r requirements.txt

# Step 6: Create a source distribution package
echo "Step 6: Creating a source distribution package..."
python3 setup.py sdist

# Step 7: Install the CLI Tool from the source distribution
echo "Step 7: Installing the CLI Tool from the source distribution..."
pip3 install .

# Check if the installation was successful
if [ $? -ne 0 ]; then
  echo "Failed to install the CLI Tool."
  exit 1
fi

# Clean up
sleep 2
clear
echo "Setup completed successfully!"
