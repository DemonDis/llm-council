ARG DOCKER_HUB

FROM ${DOCKER_HUB}python:3.12-slim-bookworm

WORKDIR /app

RUN mkdir -p /app/data/conversations

ENV HOME=/root
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

COPY . .

RUN pip --timeout=1000 install --no-cache-dir --user -r requirements.txt

CMD ["./run.sh"]
