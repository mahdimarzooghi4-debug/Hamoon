FROM alpine:3.21

ARG TARGETARCH
ARG MINIO_RELEASE=RELEASE.2025-09-07T16-13-09Z
ARG MC_RELEASE=RELEASE.2025-08-13T08-35-41Z

RUN apk add --no-cache ca-certificates curl \
    && case "${TARGETARCH}" in amd64|arm64) ;; *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; esac \
    && MINIO_ASSET="minio.linux-${TARGETARCH}.${MINIO_RELEASE}" \
    && MC_ASSET="mc.linux-${TARGETARCH}.${MC_RELEASE}" \
    && curl --fail --silent --show-error --location --retry 5 \
        --output "/tmp/${MINIO_ASSET}" \
        "https://github.com/minio/minio/releases/download/${MINIO_RELEASE}/${MINIO_ASSET}" \
    && curl --fail --silent --show-error --location --retry 5 \
        --output "/tmp/${MINIO_ASSET}.sha256sum" \
        "https://github.com/minio/minio/releases/download/${MINIO_RELEASE}/${MINIO_ASSET}.sha256sum" \
    && MINIO_SHA="$(awk '{print $1}' "/tmp/${MINIO_ASSET}.sha256sum")" \
    && echo "${MINIO_SHA}  /tmp/${MINIO_ASSET}" | sha256sum -c - \
    && curl --fail --silent --show-error --location --retry 5 \
        --output "/tmp/${MC_ASSET}" \
        "https://github.com/minio/mc/releases/download/${MC_RELEASE}/${MC_ASSET}" \
    && curl --fail --silent --show-error --location --retry 5 \
        --output "/tmp/${MC_ASSET}.sha256sum" \
        "https://github.com/minio/mc/releases/download/${MC_RELEASE}/${MC_ASSET}.sha256sum" \
    && MC_SHA="$(awk '{print $1}' "/tmp/${MC_ASSET}.sha256sum")" \
    && echo "${MC_SHA}  /tmp/${MC_ASSET}" | sha256sum -c - \
    && mv "/tmp/${MINIO_ASSET}" /usr/local/bin/minio \
    && mv "/tmp/${MC_ASSET}" /usr/local/bin/mc \
    && chmod 0755 /usr/local/bin/minio /usr/local/bin/mc \
    && rm -f /tmp/*.sha256sum

EXPOSE 9000 9001
