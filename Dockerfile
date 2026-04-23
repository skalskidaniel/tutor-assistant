FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN uv pip install --system --no-cache -e .

ENTRYPOINT ["python", "-m", "tutor.agent"]
CMD ["chat"]
