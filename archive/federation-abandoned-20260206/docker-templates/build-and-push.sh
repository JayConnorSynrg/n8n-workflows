#!/bin/bash
# Federation AIO Voice Agent - Multi-arch Build & Push Script
# Version: 1.0.0
# Purpose: Build and publish Docker images to registry

set -e
set -u

# ============================================================================
# Configuration
# ============================================================================
readonly VERSION="${1:-latest}"
readonly REGISTRY="${DOCKER_REGISTRY:-ghcr.io/synrgscaling}"
readonly IMAGE_NAME="aio-federation-template"
readonly PLATFORMS="linux/amd64,linux/arm64"
readonly BUILD_CONTEXT="."
readonly DOCKERFILE="aio-base.Dockerfile"

# Color output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# ============================================================================
# Logging
# ============================================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_fatal() {
    log_error "$*"
    exit 1
}

# ============================================================================
# Pre-flight checks
# ============================================================================
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_fatal "Docker is not installed"
    fi

    # Check Docker buildx
    if ! docker buildx version &> /dev/null; then
        log_fatal "Docker buildx is not available"
    fi

    # Check if builder exists, create if not
    if ! docker buildx inspect federation-builder &> /dev/null; then
        log_info "Creating buildx builder: federation-builder"
        docker buildx create --name federation-builder --use --platform "${PLATFORMS}"
    else
        log_info "Using existing builder: federation-builder"
        docker buildx use federation-builder
    fi

    # Check if Dockerfile exists
    if [ ! -f "${DOCKERFILE}" ]; then
        log_fatal "Dockerfile not found: ${DOCKERFILE}"
    fi

    # Check if requirements.txt exists
    if [ ! -f "requirements.txt" ]; then
        log_fatal "requirements.txt not found"
    fi

    # Check if entrypoint.sh exists
    if [ ! -f "entrypoint.sh" ]; then
        log_fatal "entrypoint.sh not found"
    fi

    log_info "All prerequisites satisfied"
}

# ============================================================================
# Copy AIO source code
# ============================================================================
prepare_build_context() {
    log_info "Preparing build context..."

    local source_dir="../../voice-agent-poc/livekit-voice-agent/src"

    if [ ! -d "${source_dir}" ]; then
        log_fatal "AIO source directory not found: ${source_dir}"
    fi

    # Copy source to build context
    log_info "Copying AIO source code from: ${source_dir}"
    rm -rf ./src
    cp -r "${source_dir}" ./src

    log_info "Build context prepared"
}

# ============================================================================
# Build and push image
# ============================================================================
build_and_push() {
    log_info "Building and pushing image..."
    log_info "Registry: ${REGISTRY}"
    log_info "Image: ${IMAGE_NAME}"
    log_info "Version: ${VERSION}"
    log_info "Platforms: ${PLATFORMS}"

    local git_sha=""
    if git rev-parse --short HEAD &> /dev/null; then
        git_sha=$(git rev-parse --short HEAD)
        log_info "Git SHA: ${git_sha}"
    fi

    local build_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build arguments
    local build_args=(
        --build-arg "BUILD_DATE=${build_date}"
        --build-arg "VERSION=${VERSION}"
        --build-arg "GIT_SHA=${git_sha}"
    )

    # Tags
    local tags=(
        --tag "${REGISTRY}/${IMAGE_NAME}:${VERSION}"
    )

    # Add 'latest' tag if VERSION is a semantic version (not 'dev')
    if [[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        tags+=(--tag "${REGISTRY}/${IMAGE_NAME}:latest")
        log_info "Adding 'latest' tag for semantic version"
    fi

    # Add git SHA tag if available
    if [ -n "${git_sha}" ]; then
        tags+=(--tag "${REGISTRY}/${IMAGE_NAME}:${git_sha}")
    fi

    # Build and push
    docker buildx build \
        --platform "${PLATFORMS}" \
        "${build_args[@]}" \
        "${tags[@]}" \
        --push \
        --file "${DOCKERFILE}" \
        "${BUILD_CONTEXT}"

    log_info "Build and push completed successfully"
}

# ============================================================================
# Display image information
# ============================================================================
display_image_info() {
    log_info "========================================="
    log_info "Image Information"
    log_info "========================================="
    log_info "Registry: ${REGISTRY}"
    log_info "Image: ${IMAGE_NAME}"
    log_info "Version: ${VERSION}"
    log_info ""
    log_info "Available tags:"
    log_info "  - ${REGISTRY}/${IMAGE_NAME}:${VERSION}"

    if [[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_info "  - ${REGISTRY}/${IMAGE_NAME}:latest"
    fi

    if git rev-parse --short HEAD &> /dev/null; then
        local git_sha=$(git rev-parse --short HEAD)
        log_info "  - ${REGISTRY}/${IMAGE_NAME}:${git_sha}"
    fi

    log_info ""
    log_info "Pull command:"
    log_info "  docker pull ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
    log_info "========================================="
}

# ============================================================================
# Cleanup
# ============================================================================
cleanup() {
    log_info "Cleaning up build context..."
    rm -rf ./src
    log_info "Cleanup complete"
}

# ============================================================================
# Main execution
# ============================================================================
main() {
    log_info "Federation AIO Docker Build & Push Script v1.0.0"
    log_info "=================================================="

    # Trap errors and cleanup
    trap cleanup EXIT

    check_prerequisites
    prepare_build_context
    build_and_push
    display_image_info

    log_info "Build process completed successfully!"
}

# Execute main
main
