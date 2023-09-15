#!/bin/bash

# Step 1: Update the system
echo "Step 1: Updating the system..."
sudo apt update
sudo apt upgrade -y

# Step 2: Download pip for Python 3
echo "Step 2: Downloading and installing pip for Python 3..."
sudo apt install python3-pip -y

# Step 3: Install dependencies from requirements.txt
echo "Step 3: Installing dependencies from requirements.txt..."
pip3 install -r requirements.txt

# Step 4: Create a source distribution package
echo "Step 4: Creating a source distribution package..."
python3 setup.py sdist

# Step 5: Install the CLI Tool from the source distribution
echo "Step 5: Installing the CLI Tool from the source distribution..."
pip3 install .

echo "Setup completed successfully!"
