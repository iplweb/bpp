# docker-bake.hcl - Parallel Docker builds for BPP
#
# Usage:
#   make build                    # Local parallel build (default)
#   make build-base               # Build only base image
#   make build-independent        # Build dbserver + webserver only
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

variable "CACHE_TYPE" {
  default = "local"  # "local" or "registry"
}

variable "GIT_SHA" {
  default = "unknown"
}

# Build groups for different scenarios
group "default" {
  targets = ["dbserver", "webserver", "appserver", "workerserver",
             "beatserver", "authserver", "denorm-queue"]
}

group "base-only" {
  targets = ["base"]
}

group "independent" {
  targets = ["dbserver", "webserver"]
}

group "app-services" {
  targets = ["appserver", "workerserver", "beatserver", "authserver", "denorm-queue"]
}

# Base image - critical path, app services depend on this
target "base" {
  dockerfile = "deploy/bpp_base/Dockerfile"
  context    = "."
  args = {
    GIT_SHA = GIT_SHA
  }
  tags       = [
    "iplweb/bpp_base:${DOCKER_VERSION}",
    "iplweb/bpp_base:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_base:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_base:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache,mode=max"
  ]
}

# Independent images - can build in parallel with base
target "dbserver" {
  dockerfile = "Dockerfile"
  context    = "deploy/dbserver"
  tags       = [
    "iplweb/bpp_dbserver:${DOCKER_VERSION}",
    "iplweb/bpp_dbserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_dbserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-dbserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_dbserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-dbserver,mode=max"
  ]
}

target "webserver" {
  dockerfile = "Dockerfile"
  context    = "deploy/webserver"
  tags       = [
    "iplweb/bpp_webserver:${DOCKER_VERSION}",
    "iplweb/bpp_webserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_webserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-webserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_webserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-webserver,mode=max"
  ]
}

# Dependent images - wait for base to complete via contexts dependency
target "appserver" {
  dockerfile = "deploy/appserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = [
    "iplweb/bpp_appserver:${DOCKER_VERSION}",
    "iplweb/bpp_appserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_appserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-appserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_appserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-appserver,mode=max"
  ]
}

target "workerserver" {
  dockerfile = "deploy/workerserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = [
    "iplweb/bpp_workerserver:${DOCKER_VERSION}",
    "iplweb/bpp_workerserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_workerserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-workerserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_workerserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-workerserver,mode=max"
  ]
}

target "beatserver" {
  dockerfile = "Dockerfile"
  context    = "deploy/beatserver"
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = [
    "iplweb/bpp_beatserver:${DOCKER_VERSION}",
    "iplweb/bpp_beatserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_beatserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-beatserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_beatserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-beatserver,mode=max"
  ]
}

target "authserver" {
  dockerfile = "deploy/authserver/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = [
    "iplweb/bpp_authserver:${DOCKER_VERSION}",
    "iplweb/bpp_authserver:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_authserver:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-authserver"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_authserver:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-authserver,mode=max"
  ]
}

target "denorm-queue" {
  dockerfile = "deploy/denorm-queue/Dockerfile"
  context    = "."
  contexts   = {
    "iplweb/bpp_base:latest" = "target:base"
  }
  tags = [
    "iplweb/bpp_denorm_queue:${DOCKER_VERSION}",
    "iplweb/bpp_denorm_queue:latest"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry"] : ["type=docker"]
  cache-from = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_denorm_queue:cache"
  ] : [
    "type=local,src=/tmp/.buildx-cache-denorm-queue"
  ]
  cache-to = CACHE_TYPE == "registry" ? [
    "type=registry,ref=iplweb/bpp_denorm_queue:cache,mode=max"
  ] : [
    "type=local,dest=/tmp/.buildx-cache-denorm-queue,mode=max"
  ]
}
