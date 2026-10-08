# Deploy unit ①. Digest inputs are mandatory and supplied ONLY from qualified
# release evidence. No tag/default is a substitute for missing image qualification.
ARG PYTHON_IMAGE_DIGEST
ARG UV_IMAGE_DIGEST
ARG LAMBDA_ADAPTER_IMAGE_DIGEST
FROM ghcr.io/astral-sh/uv:0.9.0@sha256:${UV_IMAGE_DIGEST} AS uv_binary
FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1@sha256:${LAMBDA_ADAPTER_IMAGE_DIGEST} AS lambda_adapter
FROM python:3.13.7-slim-bookworm@sha256:${PYTHON_IMAGE_DIGEST}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/runtime \
    PYTHONPATH=/app \
    PATH=/app/runtime/bin:$PATH
WORKDIR /app
COPY --from=uv_binary /uv /usr/local/bin/uv
RUN useradd --create-home --uid 10001 docsuri \
    && python -c 'import sys; assert sys.version_info >= (3, 13)'

# Copy ONLY public build inputs. In particular, never COPY the credential-bearing
# backend/ops directories wholesale. Preserve the lockfile's relative path layout.
COPY shared/python/pyproject.toml /app/shared/python/pyproject.toml
COPY shared/python/src /app/shared/python/src
COPY shared/python/README.md /app/shared/python/README.md
COPY platform_integrity/pyproject.toml /app/platform_integrity/pyproject.toml
COPY platform_integrity/src /app/platform_integrity/src
COPY platform_integrity/migrations /app/platform_integrity/migrations
COPY ops/pyproject.toml /app/ops/pyproject.toml
COPY ops/src /app/ops/src
COPY ops/README.md /app/ops/README.md
COPY backend/pyproject.toml backend/uv.lock backend/README.md /app/backend/
COPY backend/modules /app/backend/modules
COPY backend/migrations /app/backend/migrations
COPY backend/middleware /app/backend/middleware
COPY backend/*.py /app/backend/

# Build backends themselves are in the frozen build group; build isolation must
# not resolve fresh mutable requirements. Runtime-only sync removes that group.
RUN uv sync --project /app/backend --frozen --only-group build \
    && uv sync --project /app/backend --frozen --no-dev --no-editable --no-build-isolation
COPY --from=lambda_adapter /lambda-adapter /opt/extensions/lambda-adapter
USER docsuri
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
