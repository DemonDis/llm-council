ARG DOCKER_HUB

FROM ${DOCKER_HUB}node:24-slim

RUN --mount=type=bind,source=./,target=/distr/ \
   cd /distr \
&& mkdir /app \
&& cp -r package*.json vite.config.js index.html run.sh \
   node_modules src public /app

WORKDIR /app

EXPOSE 5173

CMD ["./run.sh"]
