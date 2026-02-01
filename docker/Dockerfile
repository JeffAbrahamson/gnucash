FROM ubuntu:24.04 AS compile-dev-base

RUN mkdir -p /usr/local/

WORKDIR /devsrc

# Install runtime packages
# These COPY commands only invalidate cache if the copied file has changed
COPY --chmod=755 docker/stuff/packages-runtime.sh ./
RUN ./packages-runtime.sh 2>&1 | tee /var/packages-runtime.out

# Install development packages
COPY --chmod=755 docker/stuff/packages-dev.sh ./
RUN ./packages-dev.sh 2>&1 | tee /var/packages-dev.out

# Install Python dependencies from requirements.txt
COPY bin/requirements.txt ./requirements.txt
RUN pip3 install --break-system-packages -r requirements.txt

# Create dev user for non-root operations
RUN useradd -ms /bin/bash dev

# Install gosu for privilege management
RUN apt-get update && apt-get install -y --no-install-recommends \
      gosu \
    && rm -rf /var/lib/apt/lists/*

# Add entrypoint script for UID/GID mapping
COPY --chmod=755 docker/stuff/entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]


# Development target - extends base with no changes
FROM compile-dev-base AS compile-for-dev


# Claude Code target - adds Node.js and Claude Code CLI
FROM compile-dev-base AS compile-for-claude

RUN apt-get update && apt-get install -y nodejs npm

# Install Claude Code for AI-assisted development
RUN npm install -g @anthropic-ai/claude-code


# OpenAI Codex target - adds Node.js and Codex CLI
FROM compile-dev-base AS compile-for-codex

RUN apt-get update && apt-get install -y nodejs npm

# Install OpenAI Codex CLI for AI-assisted development
RUN npm install -g @openai/codex
