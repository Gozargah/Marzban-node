#!/bin/bash

# Step 1: Update the system
echo "Step 1: Updating the system..."
sudo apt update
sudo apt upgrade -y

# Step 2: Clone the GitHub repository
echo "Step 2: Cloning the GitHub repository..."
git clone https://github.com/dry-stan/Marzban-node.git

# Search for the Marzban-node directory
marzban_node_dir=$(find / -type d -name "Marzban-node" 2>/dev/null)

if [ -z "$marzban_node_dir" ]; then
  echo "Marzban-node directory not found."
  exit 1
fi

# Step 3: Download pip for Python 3
echo "Step 3: Downloading and installing pip for Python 3..."
sudo apt install python3-pip -y

# Dynamically set the PYTHONPATH to the Marzban-node directory
PYTHONPATH_EXTENSIONS=(
  "docker_utils"
  "network_utils"
  "marzban_utils"
  "marzban_node_cli"
)

for extension in "${PYTHONPATH_EXTENSIONS[@]}"; do
  export PYTHONPATH="$marzban_node_dir/$extension:$PYTHONPATH"
done

# Change to the Marzban-node directory
echo "Changing to the Marzban-node directory..."
cd "$marzban_node_dir"

# Step 4: Install dependencies from requirements.txt
echo "Step 4: Installing dependencies from requirements.txt..."
pip3 install -r requirements.txt

# Step 5: Create a source distribution package
echo "Step 5: Creating a source distribution package..."
python3 setup.py sdist

# Step 6: Install the CLI Tool from the source distribution
echo "Step 6: Installing the CLI Tool from the source distribution..."
pip3 install .

# Re-set PYTHONPATH to the Marzban-node directory
for extension in "${PYTHONPATH_EXTENSIONS[@]}"; do
  export PYTHONPATH="$marzban_node_dir/$extension:$PYTHONPATH"
done

sleep 2
# Re-set PYTHONPATH to the Marzban-node directory
for extension in "${PYTHONPATH_EXTENSIONS[@]}"; do
  export PYTHONPATH="$marzban_node_dir/$extension:$PYTHONPATH"
done
clear
echo "Setup completed successfully!"

