#!/bin/bash

# Step 1: Update the system
echo "Step 1: Updating the system..."
sudo apt update
sudo apt upgrade -y
sudo apt install python3-pip -y
sudo apt install git -y
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

# Change to the Marzban-node/cli directory
echo "Step 3: Changing to the Marzban-node/cli directory..."
cd "$marzban_node_dir/cli"

# Step 4: Install dependencies from requirements.txt
echo "Step 4: Installing dependencies from requirements.txt..."
pip3 install -r requirements.txt

# Step 5: Create a source distribution package
echo "Step 5: Creating a source distribution package..."
python3 setup.py sdist

# Step 6: Install the CLI Tool from the source distribution
echo "Step 6: Installing the CLI Tool from the source distribution..."
pip3 install .

# Check if the installation was successful
if [ $? -ne 0 ]; then
  echo "Failed to install the CLI Tool."
  exit 1
fi

# Configuration
completion_script_path="/var/opt/Marzban-node/cli/marzban-node-completion.sh"
shell_rc_file="$HOME/.bashrc" # Adjust to match the user's shell configuration file

# Function to add completion script to the shell configuration
add_completion_to_shell() {
    if [[ -f "$shell_rc_file" ]]; then
        if grep -q "source $completion_script_path" "$shell_rc_file"; then
            echo "Auto-completion is already configured in $shell_rc_file."
        else
            echo "Adding auto-completion configuration to $shell_rc_file..."
            echo "source $completion_script_path" >> "$shell_rc_file"
            echo "Auto-completion configuration added to $shell_rc_file. Please restart your shell to apply the changes."
        fi
    else
        echo "Shell configuration file ($shell_rc_file) not found. Please configure auto-completion manually."
    fi
}

# Auto-completion script setup
if [[ -f "$completion_script_path" ]]; then
    echo "Auto-completion script found: $completion_script_path"
    add_completion_to_shell
else
    echo "Auto-completion script ($completion_script_path) not found. Please create the completion script manually."
fi

# Source the .bashrc file
source ~./bashrc

# Clean up
sleep 2

clear
echo "Setup completed successfully!"
