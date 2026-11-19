FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
WORKDIR /app
COPY pyproject.toml README.md requirements.lock ./
COPY avtriage ./avtriage
COPY tools ./tools
COPY assets ./assets
COPY recipes ./recipes
COPY viewer ./viewer
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
EXPOSE 8000
CMD ["sh", "-c", "avtriage demo --workspace /workspace && exec avtriage serve --workspace /workspace --host 0.0.0.0"]
