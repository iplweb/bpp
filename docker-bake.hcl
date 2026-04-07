# docker-bake.hcl - Parallel Docker builds for BPP
#
# Usage:
#   make build                    # Local parallel build (default)
#   make build-base               # Build only base image
#   make build-independent        # Build dbserver only
#   docker buildx bake --print    # Show build plan without executing
#
# Variables can be overridden via environment or --set flag:
#   DOCKER_VERSION=202601.1234 make build
#   docker buildx bake --set PUSH=true

variable "DOCKER_VERSION" {
  default = "latest"
}

variable "PLATFORM" {
  default = "linux/amd64"
}

variable "PUSH" {
  default = false
}

variable "GIT_SHA" {
  default = "unknown"
}

variable "TAG_LATEST" {
  default = "true"
}

# Build groups for different scenarios
group "default" {
  targets = ["dbserver", "appserver", "workerserver",
             "beatserver", "authserver", "denorm-queue"]
}

group "base-only" {
  targets = ["base"]
}

group "independent" {
  targets = ["dbserver"]
}

group "app-services" {
  targets = ["appserver", "workerserver", "beatserver", "authserver", "denorm-queue"]
}

# Base image - critical path, app services depend on this
target "base" {
  dockerfile = "docker/bpp_base/Dockerfile"
  context    = "."
  args = {
    GIT_SHA = GIT_SHA
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_base:${DOCKER_VERSION}",
    "iplweb/bpp_base:latest"
  ] : [
    "iplweb/bpp_base:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

# Independent images - can build in parallel with base
target "dbserver" {
  dockerfile = "Dockerfile"
  context    = "docker/dbserver"
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_dbserver:${DOCKER_VERSION}",
    "iplweb/bpp_dbserver:latest"
  ] : [
    "iplweb/bpp_dbserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

# Dependent images - wait for base to complete via contexts dependency
target "appserver" {
  dockerfile = "docker/appserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_appserver:${DOCKER_VERSION}",
    "iplweb/bpp_appserver:latest"
  ] : [
    "iplweb/bpp_appserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

target "workerserver" {
  dockerfile = "docker/workerserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_workerserver:${DOCKER_VERSION}",
    "iplweb/bpp_workerserver:latest"
  ] : [
    "iplweb/bpp_workerserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

target "beatserver" {
  dockerfile = "Dockerfile"
  context    = "docker/beatserver"
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_beatserver:${DOCKER_VERSION}",
    "iplweb/bpp_beatserver:latest"
  ] : [
    "iplweb/bpp_beatserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

target "authserver" {
  dockerfile = "docker/authserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_authserver:${DOCKER_VERSION}",
    "iplweb/bpp_authserver:latest"
  ] : [
    "iplweb/bpp_authserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}

target "denorm-queue" {
  dockerfile = "docker/denorm-queue/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_denorm_queue:${DOCKER_VERSION}",
    "iplweb/bpp_denorm_queue:latest"
  ] : [
    "iplweb/bpp_denorm_queue:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
}
