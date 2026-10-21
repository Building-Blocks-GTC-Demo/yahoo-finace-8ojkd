FROM node:20-alpine AS builder

ARG COMMIT_SHA=96183d6aef0298e36fb8c4ad19f0c4ca0d752d63

RUN apk add --no-cache git

WORKDIR /app

RUN git clone https://github.com/langchain-ai/deep-agents-ui.git . && \
    git checkout ${COMMIT_SHA}

RUN yarn install --frozen-lockfile

# Files that do not exist upstream, so they cannot conflict. The guard keeps that
# invariant honest: if upstream ever adds one of these paths, stop instead of
# silently clobbering it.
COPY additions/ /additions/
RUN set -e; cd /additions; \
    for f in $(find . -type f); do \
      if [ -e "/app/$f" ]; then echo "ERROR: additions/${f#./} now exists upstream" >&2; exit 1; fi; \
    done; \
    cp -R /additions/. /app/

# In-place edits to upstream files. A failure here means COMMIT_SHA moved and the
# patches need regenerating; see README.md.
COPY patches/ /patches/
RUN cd /app && git apply --verbose /patches/*.patch

RUN yarn build

# --- Runtime ---
FROM node:20-slim

WORKDIR /app

COPY --from=builder /app/package.json /app/yarn.lock ./
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["yarn", "start"]
