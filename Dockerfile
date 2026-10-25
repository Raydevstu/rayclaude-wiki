FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY tier1 ./tier1
RUN pip install .
COPY skills ./skills
RUN useradd -r -u 10001 agent && mkdir -p /data /sandbox && chown agent /data /sandbox
USER agent
ENV TIER1_HOME=/data TIER1_DB=/data/tier1.db TIER1_SKILLS_DIR=/app/skills TIER1_SANDBOX_DIR=/sandbox
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"
CMD ["tier1","serve","--host","0.0.0.0","--port","8000"]
