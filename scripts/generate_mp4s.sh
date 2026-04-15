#!/bin/bash
BATCH_DIR="/root/Project/MimicKit/output/img/ase_7case_tmux_20260312_235006"
OUTPUT_DIR="/root/Project/MimicKit/output/mp4s/ase_7case_tmux_20260312_235006"

mkdir -p "$OUTPUT_DIR"

for case_dir in "$BATCH_DIR"/*/; do
    case_name=$(basename "$case_dir")
    frames_dir="${case_dir}render/frames"
    
    if [ -d "$frames_dir" ]; then
        output_mp4="$OUTPUT_DIR/${case_name}.mp4"
        
        echo "Converting $case_name to mp4..."
        ffmpeg -framerate 30 \
               -pattern_type glob \
               -i "$frames_dir/frame_*.png" \
               -c:v libx264 \
               -pix_fmt yuv420p \
               -y \
               "$output_mp4"
        
        echo "✓ Created: $output_mp4"
    fi
done

echo "All conversions complete!"
