# Claude Code Telegram Bot — VPS deploy image.
#
# Bundles the Python bot + Anthropic Claude Code CLI in one image so the
# bot's SDK-mode invocations have `claude` on PATH. Auth state is supplied
# via a host-mounted /root/.claude/ volume (one-time `claude login` run
# during bootstrap; persists across rebuilds).

FROM python:3.11-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

# Node.js 20 (claude CLI is npm-distributed) + git (bot does git ops in repos)
# + docker-ce-cli + compose plugin (bot runs `docker compose` against the
# host socket bind-mounted at /var/run/docker.sock).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg git ffmpeg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@2.1.123

# Bot runs as root; bind-mounted host repos are owned by ubuntu (uid 1001).
# Without this, git refuses with "dubious ownership". Bot needs to read +
# write any repo on the host, so allow all paths.
RUN git config --system --add safe.directory '*'

RUN pip install poetry==2.1.3

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# Voice (STT): openai-whisper provides the `whisper` CLI used by
# src/bot/features/voice_handler.py when VOICE_PROVIDER=local.
# Pulls torch (~1.5GB on aarch64) — kept out of poetry to make the
# voice-extras toggle explicit at the image-layer level.
RUN pip install --no-cache-dir openai-whisper==20240930

COPY src/ ./src/
COPY README.md ./

RUN mkdir -p /app/data /root/.claude /root/.cache/whisper

EXPOSE 8088

CMD ["python", "-m", "src.main"]
