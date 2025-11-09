#!/bin/bash

# GitBackup - Auto-installer
# One-liner install: curl -sSL https://raw.githubusercontent.com/giobi/gitbackup/main/install.sh | bash

set -e

echo ""
echo "🔧 GitBackup Auto-installer"
echo "==========================="
echo ""

# Check dependencies
for cmd in git curl python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ $cmd is required but not installed"
        echo "   Install it and try again"
        exit 1
    fi
done

# Ask install location
read -p "📂 Install directory [./gitbackup]: " install_dir
install_dir=${install_dir:-./gitbackup}

# Expand tilde
install_dir=$(eval echo "$install_dir")

# Check if already exists
if [ -d "$install_dir" ]; then
    echo "⚠️  Directory $install_dir already exists!"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Installation cancelled"
        exit 1
    fi
else
    # Create parent dir if needed
    mkdir -p "$(dirname "$install_dir")"
fi

# Clone or update repo
if [ -d "$install_dir/.git" ]; then
    echo "📥 Updating existing installation..."
    cd "$install_dir"
    git pull --quiet
else
    echo "📥 Downloading GitBackup..."
    git clone --quiet https://github.com/giobi/gitbackup.git "$install_dir"
    cd "$install_dir"
fi

echo "✅ GitBackup downloaded to $install_dir"
echo ""

# Make scripts executable
chmod +x backup.sh setup.sh install.sh

# Run setup
echo "🔧 Starting interactive setup..."
echo ""
./setup.sh

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ GitBackup installed successfully!"
    echo ""
    echo "📝 Installed to: $install_dir"
    echo ""
    echo "📚 Usage:"
    echo "   cd $install_dir"
    echo "   ./backup.sh    - Run backup manually"
    echo ""
    echo "📋 See README.md for advanced features"
else
    echo "❌ Setup failed"
    echo "   Check logs and try again"
fi

echo ""
