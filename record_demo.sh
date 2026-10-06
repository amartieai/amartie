#!/bin/bash
# Record the JEV gate demo — terminal + ffmpeg screen capture
set -e

DEMO_DIR="/home/atlas/amartie-clone-temp"
OUTPUT_DIR="/home/atlas/.hermes/profiles/orchestrator/cache/scratch"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
VIDEO_OUT="${OUTPUT_DIR}/jev_gate_demo_${TIMESTAMP}.mp4"
TERMINAL_ID=""

# Cleanup function
cleanup() {
    if [ -n "$TERMINAL_ID" ]; then
        kill "$TERMINAL_ID" 2>/dev/null || true
    fi
    # Kill any lingering ffmpeg
    pkill -f "ffmpeg.*x11grab" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== AMARTIE JEV Gate Demo Recording ==="
echo "Output: $VIDEO_OUT"
echo ""

# Open a clean terminal window at a fixed position
echo "[1/3] Opening terminal..."
gnome-terminal --geometry=100x40+100+100 --title="AMARTIE JEV 9-Judge Gate Demo" -- bash -c "
    cd $DEMO_DIR
    echo ''
    echo '  Starting demo in 3 seconds...'
    sleep 3
    python3 demo_jev_gate.py
    echo ''
    echo '  Demo complete. Press any key to close.'
    read -n 1
" &
TERMINAL_ID=$!

# Wait for terminal to appear
sleep 2

# Start recording
echo "[2/3] Starting screen recording..."
ffmpeg -y -f x11grab -r 30 -s 1920x1080 -i :0.0 \
    -codec:v libx264 -preset fast -crf 23 \
    -pix_fmt yuv420p \
    "$VIDEO_OUT" &
FFMPEG_PID=$!

# Wait for demo to run (script has ~5s of sleeps + output)
echo "[3/3] Recording demo..."
sleep 12

# Stop recording
echo "Stopping recording..."
kill $FFMPEG_PID 2>/dev/null || true
wait $FFMPEG_PID 2>/dev/null || true

# Close terminal
kill $TERMINAL_ID 2>/dev/null || true
TERMINAL_ID=""

# Verify output
if [ -f "$VIDEO_OUT" ]; then
    SIZE=$(stat -c%s "$VIDEO_OUT")
    echo ""
    echo "=== Recording complete ==="
    echo "File: $VIDEO_OUT"
    echo "Size: $SIZE bytes"
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_OUT" 2>/dev/null || echo "Duration: unknown"
else
    echo "ERROR: Video file not created"
    exit 1
fi
