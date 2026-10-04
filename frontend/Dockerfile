FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/ ./
RUN npm install --ignore-scripts --no-audit --no-fund \
    && npm run build

FROM nginx:alpine

ARG HAMOON_APPLICATION_VERSION=0.1.0
ARG HAMOON_GIT_COMMIT=development

ENV HAMOON_APPLICATION_VERSION="${HAMOON_APPLICATION_VERSION}" \
    HAMOON_GIT_COMMIT="${HAMOON_GIT_COMMIT}"

LABEL org.opencontainers.image.version="${HAMOON_APPLICATION_VERSION}" \
      org.opencontainers.image.revision="${HAMOON_GIT_COMMIT}"

RUN apk upgrade --no-cache

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/docker-entrypoint.d/40-hamoon-runtime-config.sh /docker-entrypoint.d/40-hamoon-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/40-hamoon-runtime-config.sh
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
