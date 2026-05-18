#!/bin/bash
# Automatically use the virtual environment to run the app

if [ -d "venv" ]; then
    echo "Using virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found. Please create it first."
    exit 1
fi

echo "Starting the application..."
python main.py
