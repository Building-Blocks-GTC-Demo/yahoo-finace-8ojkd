# Deep Agents UI customizations

The chat UI is upstream [langchain-ai/deep-agents-ui](https://github.com/langchain-ai/deep-agents-ui)
pinned to `COMMIT_SHA` in the `Dockerfile`. The source is not vendored here — the
Docker build clones it and then applies only our delta.

Two directories, each with one invariant:

| Directory | Invariant | Applied by |
|-----------|-----------|------------|
| `additions/` | Paths must **not** exist upstream | `cp`, after a guard that fails the build if the path appeared upstream |
| `patches/` | Unified diffs against files that **do** exist upstream | `git apply` |

Prefer `additions/` — a new module cannot conflict. Reach for a patch only for
the lines that must change inside an upstream file.

## Current customizations

- `additions/src/app/utils/routedModel.ts` — reads Switchyard's selected-model
  response header off a message and resolves it to the model's display name and
  color from the `blockyModels` query param the Blocky Bits SPA puts on the iframe URL.
- `patches/0001-chat-message-model-rail.patch` — draws a model-colored vertical
  rail on each assistant response and tool-call group in `ChatMessage.tsx`, so a
  Switchyard tier change is visible in the transcript. Every response is labelled
  with the model that served it. The header arrives only once a message finishes
  streaming, so the label row and rail gutter are held open from first paint and
  a finished answer does not reflow.

## Editing a patched file

Patched files cannot be edited in this repo — work in a scratch clone and
regenerate the diff:

```bash
git clone https://github.com/langchain-ai/deep-agents-ui.git /tmp/dau
cd /tmp/dau && git checkout <COMMIT_SHA from the Dockerfile>
cp -R ~/blocky-bits/deep-agents-ui/additions/. .
git apply ~/blocky-bits/deep-agents-ui/patches/*.patch

# make your edits, then:
git diff -- src/app/components/ChatMessage.tsx \
  > ~/blocky-bits/deep-agents-ui/patches/0001-chat-message-model-rail.patch
```

Rebuild with `make chat-ui-image` (or `docker build -t chat-ui deep-agents-ui`).
The build is the only type check these files get — they sit outside any
`tsconfig.json` here, so the editor cannot resolve their `@/` imports.

## When `git apply` fails

It means `COMMIT_SHA` moved and upstream has rewritten the lines a patch
depends on. That failure is the point: regenerate the patch against the new
commit rather than working around it.
