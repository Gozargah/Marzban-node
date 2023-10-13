#!/bin/bash

# Define the main repository and the fork repository URLs
main="https://github.com/Gozargah/Marzban-node.git"
fork="https://github.com/dry-stan/Marzban-node.git"

# Define a temporary directory for storing repositories
temp_dir="/tmp/update_fork"

# Create the temporary directory if it doesn't exist
mkdir -p "$temp_dir"

# Function to update the main repository to my fork
update_repo() {
  local repo_dir="$1"
  
  if [ -d "$repo_dir" ]; then
    echo "Updating repository: $repo_dir"
    cd "$repo_dir" || return
    git remote add your_fork "$fork"
    git fetch your_fork

    # Update all branches to my fork
    for branch in $(git branch -a | sed 's/remotes\/your_fork\///'); do
      git checkout "$branch"
      git pull your_fork "$branch"
    done

    cd - || return
  fi
}

# Find all directories named "Marzban-node"
repos=$(find / -type d -name "Marzban-node")

# Loop through the repositories and update them to my fork
for repo in $repos; do
  update_repo "$repo"
done

# Clean up
rm -rf "$temp_dir"

echo "Update complete!"
