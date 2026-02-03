#!/bin/bash
# Docker build script for wps-bot
# Usage: ./build.sh [major|minor|patch|version]

set -e

IMAGE_NAME="wps-bot"
VERSION_FILE=".version"
DOCKERFILE="Dockerfile"
BUMP_TYPE="${1:-patch}"

# Get current version
get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "0.0.0"
    fi
}

# Bump version
bump_version() {
    local version="$1"
    local type="$2"
    
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)
    local patch=$(echo "$version" | cut -d. -f3)
    
    case "$type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            if echo "$type" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
                echo "$type"
                return
            else
                echo "Error: Invalid version format: $type" >&2
                exit 1
            fi
            ;;
    esac
    
    echo "${major}.${minor}.${patch}"
}

# Main
echo "======================================"
echo "Docker Build Script"
echo "======================================"

CURRENT_VERSION=$(get_current_version)
NEW_VERSION=$(bump_version "$CURRENT_VERSION" "$BUMP_TYPE")

echo ""
echo "Version:"
echo "  Current: $CURRENT_VERSION"
echo "  New:     $NEW_VERSION"

echo "$NEW_VERSION" > "$VERSION_FILE"
echo "  Saved to: $VERSION_FILE"

IMAGE_TAG="${IMAGE_NAME}:${NEW_VERSION}"
IMAGE_LATEST="${IMAGE_NAME}:latest"

echo ""
echo "Building:"
echo "  Image: $IMAGE_TAG"
echo "  Dockerfile: $DOCKERFILE"

docker build -f "$DOCKERFILE" -t "$IMAGE_TAG" -t "$IMAGE_LATEST" .

if [ $? -ne 0 ]; then
    echo "Error: Build failed!" >&2
    exit 1
fi

echo "  [OK] Build success"

echo ""
echo "Saving:"
TAR_FILE="${IMAGE_NAME}-${NEW_VERSION}.tar"
echo "  File: $TAR_FILE"

docker save "$IMAGE_TAG" -o "$TAR_FILE"

if [ $? -ne 0 ]; then
    echo "Error: Save failed!" >&2
    exit 1
fi

FILE_SIZE=$(du -h "$TAR_FILE" | cut -f1)
echo "  [OK] Saved (size: $FILE_SIZE)"

echo ""
read -p "Compress? (y/N): " COMPRESS
if [[ "$COMPRESS" =~ ^[Yy]$ ]]; then
    echo "  Compressing..."
    gzip -f "$TAR_FILE"
    COMPRESSED_SIZE=$(du -h "${TAR_FILE}.gz" | cut -f1)
    echo "  [OK] Compressed (size: $COMPRESSED_SIZE)"
    TAR_FILE="${TAR_FILE}.gz"
fi

echo ""
echo "======================================"
echo "Done!"
echo "======================================"
echo ""
echo "Image:"
echo "  Tag:    $IMAGE_TAG"
echo "  Latest: $IMAGE_LATEST"
echo "  File:   $TAR_FILE"
echo ""
echo "Usage:"
echo "  docker load -i $TAR_FILE"
echo "  docker run -d --name wps-bot -p 8080:8080 $IMAGE_TAG"
echo ""
