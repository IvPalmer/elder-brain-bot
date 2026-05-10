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

# Git identity for `git commit` from inside the bot. Without a user.name +
# user.email anywhere, commit aborts. Bot commits show up authored by the
# bot identity; Co-Authored-By the user in the actual Claude session.
RUN git config --system user.name  "elder-brain-bot" \
 && git config --system user.email "bot@grooveops.dev"

# SSH state for root-in-container so `ssh git@github.com` (used by git
# push) and other host-key-protected SSHs work without manual accept:
#   - known_hosts pinned to GitHub's published host keys (NOT ssh-keyscan,
#     which is TOFU at build time and would bake in whatever the build
#     host happens to receive). Source:
#     https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
#   - config maps github.com → identity at /home/ubuntu/.ssh/id_lake
#     (bind-mounted from host; same key the ubuntu user uses, registered
#     as a github account SSH key for IvPalmer on 2026-05-10).
#   - StrictHostKeyChecking yes for github since the key is now pinned.
#   - Tailnet host alias `mac-studio` → 100.92.77.68 (Raphaels-Mac-Studio).
#     Use a named alias instead of wildcarding the 100.64.0.0/10 CGNAT
#     range so we don't paint id_lake at every tailnet host the bot
#     might ever talk to. Add more Host blocks for other tailnet
#     machines if the bot grows reach.
RUN mkdir -p /root/.ssh \
 && chmod 700 /root/.ssh \
 && printf '%s\n' \
        'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' \
        'github.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=' \
        'github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=' \
        > /root/.ssh/known_hosts \
 && printf '%s\n' \
        'Host github.com' \
        '    HostName github.com' \
        '    User git' \
        '    IdentityFile /home/ubuntu/.ssh/id_lake' \
        '    IdentitiesOnly yes' \
        '    StrictHostKeyChecking yes' \
        '    UserKnownHostsFile /root/.ssh/known_hosts' \
        '' \
        'Host mac-studio' \
        '    HostName 100.92.77.68' \
        '    User palmer' \
        '    IdentityFile /home/ubuntu/.ssh/id_lake' \
        '    IdentitiesOnly yes' \
        '    StrictHostKeyChecking accept-new' \
    > /root/.ssh/config \
 && chmod 600 /root/.ssh/config /root/.ssh/known_hosts

RUN pip install poetry==2.1.3

WORKDIR /app

COPY pyproject.toml poetry.lock ./
# `voice` extras pull in `openai` + `mistralai` — the openai pkg is what
# tts_handler.py uses to talk to Kokoro's OpenAI-compatible /v1/audio/speech.
# Without this, ENABLE_VOICE_REPLIES=true logs "openai is not installed"
# and silently drops the audio reply.
RUN poetry install --only main --no-root --extras voice

# Voice (STT): openai-whisper provides the `whisper` CLI used by
# src/bot/features/voice_handler.py when VOICE_PROVIDER=local.
# Pulls torch (~1.5GB on aarch64) — kept out of poetry to make the
# voice-extras toggle explicit at the image-layer level.
#
# openai-whisper still ships a setup.py that imports `pkg_resources`,
# which setuptools 81+ removed. Pin setuptools<81 in build isolation
# via PIP_CONSTRAINT so the build wheel step finds pkg_resources.
RUN echo "setuptools<81" > /tmp/whisper-constraints.txt \
 && PIP_CONSTRAINT=/tmp/whisper-constraints.txt \
    pip install --no-cache-dir openai-whisper==20240930 \
 && rm /tmp/whisper-constraints.txt

COPY src/ ./src/
COPY README.md ./

RUN mkdir -p /app/data /root/.claude /root/.cache/whisper

EXPOSE 8088

CMD ["python", "-m", "src.main"]
