# Container host for the local HTTP server. No dependencies to install: stdlib only.
FROM python:3.12-slim
WORKDIR /app
COPY src/ ./src/
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
EXPOSE 8765
USER nobody
CMD ["python", "-m", "archon_demo.server", "--host", "0.0.0.0", "--port", "8765"]
