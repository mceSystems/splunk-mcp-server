FROM python:3.12-slim

WORKDIR /app

# Install package first (layer-caches dependencies)
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Run as non-root
RUN useradd -m splunk
USER splunk

# MCP servers communicate over stdio — the container must be run with
# stdin/stdout attached (e.g. via Claude Desktop or a wrapper script).
ENTRYPOINT ["python", "-m", "splunk_mcp.server"]
