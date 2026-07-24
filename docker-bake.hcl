# docker-bake.hcl - Parallel Docker builds for BPP
#
# Obraz dbservera (iplweb/bpp_dbserver) jest budowany w osobnym repo:
# https://github.com/iplweb/bpp-dbserver
#
# Usage:
#   make build                    # Local parallel build (default)
#   make build-base               # Build only base image
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

# Rozróżnienie release vs developer build. Master release -> "release"
# (stopka pokazuje tylko numer wersji); PR/feature/lokalne -> "dev"
# (stopka dokleja `(<image_tag>, commit XXXXXXX)` po wersji, dla łatwego
# namierzenia którego commitu/buildu dotyczy obraz, gdy tag jest
# niejednoznaczny).
variable "BPP_BUILD_FLAVOR" {
  default = "dev"
}

# Kanoniczny tag obrazu (np. "119-merge", nazwa brancha, "202604.1364"
# dla mastera). Workflow przekazuje wartość z steps.tag.outputs.final_tag.
variable "BPP_IMAGE_TAG" {
  default = "unknown"
}

# Opcjonalny alias nazwy brancha dla starszych obrazow PR lub buildow lokalnych.
# Biezacy workflow CI pozostawia go pusty.
variable "BPP_BRANCH_TAG" {
  default = ""
}

variable "TAG_LATEST" {
  default = "true"
}

# R16: zstd compression przy pushu do rejestru (~20-30% mniejszy transfer
# pull/push niz gzip). Dotyczy TYLKO `type=registry` — lokalny `type=docker`
# zapisuje uncompressed do daemon storage. Override wartosci:
#   COMPRESSION=gzip make build              # stare zachowanie
#   COMPRESSION_LEVEL=9 make build           # wyzsza kompresja, wolniejszy push
# Docker Hub wspiera zstd od 2023; klienci z Docker 23+ pullna natywnie,
# starsi dostana gzip fallback (koszt po stronie rejestru).
variable "COMPRESSION" {
  default = "zstd"
}

variable "COMPRESSION_LEVEL" {
  default = "3"
}

# Build groups for different scenarios
group "default" {
  targets = ["appserver", "workerserver",
             "beatserver", "authserver", "denorm-queue"]
}

group "base-only" {
  targets = ["base"]
}

group "app-services" {
  targets = ["appserver", "workerserver", "beatserver", "authserver", "denorm-queue"]
}

# Base image - critical path, app services depend on this
target "base" {
  dockerfile = "docker/bpp_base/Dockerfile"
  context    = "."
  args = {
    GIT_SHA          = GIT_SHA
    BPP_BUILD_FLAVOR = BPP_BUILD_FLAVOR
    BPP_IMAGE_TAG    = BPP_IMAGE_TAG
    BPP_BRANCH_TAG   = BPP_BRANCH_TAG
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_base:${DOCKER_VERSION}",
    "iplweb/bpp_base:latest"
  ] : [
    "iplweb/bpp_base:${DOCKER_VERSION}"
  ]
  # Always rebuild base from scratch — Docker Build Cloud's layer cache has
  # produced stale bpp_base images (missing files added in fresh COPY lines).
  # Package downloads remain fast thanks to cache mounts inside
  # docker/bpp_base/Dockerfile (apt-cache, apt-lists, uv-cache, npm-cache,
  # yarn-cache) which persist across --no-cache builds.
  no-cache  = true
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}

# Dependent images - wait for base to complete via contexts dependency
target "appserver" {
  dockerfile = "docker/appserver/Dockerfile"
  context    = "."
  args = {
    BPP_BASE_TAG = DOCKER_VERSION
  }
  contexts = {
    "iplweb/bpp_base:${DOCKER_VERSION}" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_appserver:${DOCKER_VERSION}",
    "iplweb/bpp_appserver:latest"
  ] : [
    "iplweb/bpp_appserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}

target "workerserver" {
  dockerfile = "docker/workerserver/Dockerfile"
  context    = "."
  args = {
    BPP_BASE_TAG = DOCKER_VERSION
  }
  contexts = {
    "iplweb/bpp_base:${DOCKER_VERSION}" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_workerserver:${DOCKER_VERSION}",
    "iplweb/bpp_workerserver:latest"
  ] : [
    "iplweb/bpp_workerserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}

target "beatserver" {
  dockerfile = "docker/beatserver/Dockerfile"
  context    = "."
  args = {
    BPP_BASE_TAG = DOCKER_VERSION
  }
  contexts = {
    "iplweb/bpp_base:${DOCKER_VERSION}" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_beatserver:${DOCKER_VERSION}",
    "iplweb/bpp_beatserver:latest"
  ] : [
    "iplweb/bpp_beatserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}

target "authserver" {
  dockerfile = "docker/authserver/Dockerfile"
  context    = "."
  args = {
    BPP_BASE_TAG = DOCKER_VERSION
  }
  contexts = {
    "iplweb/bpp_base:${DOCKER_VERSION}" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_authserver:${DOCKER_VERSION}",
    "iplweb/bpp_authserver:latest"
  ] : [
    "iplweb/bpp_authserver:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}

target "denorm-queue" {
  dockerfile = "docker/denorm-queue/Dockerfile"
  context    = "."
  args = {
    BPP_BASE_TAG = DOCKER_VERSION
  }
  contexts = {
    "iplweb/bpp_base:${DOCKER_VERSION}" = "target:base"
  }
  tags = TAG_LATEST == "true" ? [
    "iplweb/bpp_denorm_queue:${DOCKER_VERSION}",
    "iplweb/bpp_denorm_queue:latest"
  ] : [
    "iplweb/bpp_denorm_queue:${DOCKER_VERSION}"
  ]
  platforms = [PLATFORM]
  output    = PUSH ? ["type=registry,compression=${COMPRESSION},compression-level=${COMPRESSION_LEVEL},force-compression=true"] : ["type=docker"]
}
