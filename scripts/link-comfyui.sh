#!/usr/bin/env bash
set -eu

if [ "$#" -ne 1 ]; then
  printf 'Usage: %s /path/to/ComfyUI\n' "$0" >&2
  exit 1
fi
comfyui_root="$1"
extension_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
extension_link="$comfyui_root/custom_nodes/ComfyUI-AstroPhotoFlow"

if [ ! -d "$comfyui_root/custom_nodes" ]; then
  printf 'ComfyUI custom_nodes directory not found: %s\n' "$comfyui_root/custom_nodes" >&2
  exit 1
fi

if [ -e "$extension_link" ] || [ -L "$extension_link" ]; then
  printf 'Extension path already exists: %s\n' "$extension_link" >&2
  exit 1
fi

ln -s "$extension_root" "$extension_link"
printf 'Linked AstroPhotoFlow into %s\n' "$extension_link"
