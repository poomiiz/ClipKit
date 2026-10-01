#!/bin/sh
# fit.sh SRC START DUR OUT  -> 1080x1920, whole frame visible (no crop), blurred fill top/bottom
F="split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.08[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p"
ffmpeg -v error -y -ss "$2" -i "$1" -t "$3" -an -vf "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,$F" -r 30 -c:v libx264 -crf 18 -preset fast "$4" && echo "ok $(basename "$4")"
