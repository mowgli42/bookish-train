# Phase 1 assessment tools: curl + Python + requests. Run scenario or individual scripts.
# Build from repo root: docker build -f scripts/tools/Dockerfile -t phase1-tools .
FROM alpine:3.19
RUN apk add --no-cache curl python3 py3-pip \
  && pip3 install --break-system-packages requests
WORKDIR /workspace
COPY scripts /workspace/scripts
COPY tests   /workspace/tests
RUN chmod +x /workspace/scripts/phase1-scenario.sh \
  && chmod +x /workspace/scripts/tools/*.sh
ENV CATCHER_URL=http://catcher:8000
CMD ["/workspace/scripts/phase1-scenario.sh"]
