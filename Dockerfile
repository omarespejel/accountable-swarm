FROM python:3.11-slim

WORKDIR /app

COPY accountable_swarm ./accountable_swarm
COPY fixtures ./fixtures
COPY scripts ./scripts
COPY README.md LICENSE ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

RUN python3 scripts/build_swarm_demo_bundle.py

CMD ["python3", "scripts/serve_demo.py", "--host", "0.0.0.0", "--port", "8000"]
