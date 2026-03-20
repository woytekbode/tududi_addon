# CLAUDE.md — Project Context for AI Assistants

## How to Use This File

**This file lives on the `claude-context` branch** of `woytekbode/tududi_addon`. It is NOT on `main`. This prevents sync conflicts between the fork and C2gl's upstream repo.

- To read: `github:get_file_contents` with `branch: "claude-context"`
- To update: `github:create_or_update_file` with `branch: "claude-context"`
- Never push CLAUDE.md to `main` or to PR branches — it causes fork divergence.
- The project instructions should say: "read CLAUDE.md from the `claude-context` branch of woytekbode/tududi_addon"

## GitHub MCP API Access — READ THIS FIRST

The GitHub MCP connection is authenticated as **woytekbode**. This determines what Claude can and cannot do:

**Can do (woytekbode repos):**
- Read files, PRs, issues, comments on any public repo
- Create/push files, create branches on `woytekbode/*` repos
- Create cross-fork PRs from `woytekbode/tududi_addon` → `C2gl/tududi_addon`

**Cannot do (C2gl repos — even though woytekbode is co-maintainer):**
- Push files or create branches directly on `C2gl/tududi_addon`
- Edit PR descriptions, add comments, or update issues on `C2gl/tududi_addon`
- Merge PRs on `C2gl/tududi_addon`
- Trigger GitHub Actions workflows on any repo

**Workflow implications:**
- All code changes go through the fork → PR to C2gl. Never try to push directly to C2gl.
- The user must manually: sync the fork with C2gl, merge PRs on C2gl, run builder workflows, edit PR descriptions on C2gl.
- **The fork's `main` must be synced with C2gl's `main` before creating new PR branches.** If behind, cross-fork PRs will fail. Ask the user to sync: GitHub → woytekbode/tududi_addon → "Sync fork".
- PR branch naming convention: `pr/c2gl-<description>` for branches intended as PRs to C2gl.
- **Never push CLAUDE.md or fork-only files to `main`.** They cause the fork to diverge from upstream, breaking future syncs and PR creation.

## Overview

This is a fork of [C2gl/tududi_addon](https://github.com/C2gl/tududi_addon), used for testing changes against a live Home Assistant install before submitting PRs upstream.

The addon wraps [chrisvel/tududi](https://github.com/chrisvel/tududi) (a self-hosted task manager) as an HA addon. The upstream repo contains two addon variants, both on `main` branch side by side:

- **`tududi-addon/`** — Production addon.
- **`tududi-addon-dev/`** — Dev addon, tracks upstream pre-releases.

**woytekbode is a co-maintainer of C2gl/tududi_addon** (granted by C2gl). The user can merge PRs, run the builder workflow, and manage the upstream repo via the GitHub web UI — but the MCP API cannot do these things (see above).

## Repos

| Repo | Role |
|------|------|
| [chrisvel/tududi](https://github.com/chrisvel/tududi) | Upstream app (Node/React task manager) |
| [woytekbode/tududi](https://github.com/woytekbode/tududi) | Fork of upstream app (for PRs to chrisvel) |
| [C2gl/tududi_addon](https://github.com/C2gl/tududi_addon) | Upstream HA addon (woytekbode is co-maintainer) |
| [woytekbode/tududi_addon](https://github.com/woytekbode/tududi_addon) | Fork of addon (testing ground, MCP can write here) |

## How to Publish a Release

HA addon updates are a two-step process:

1. **Merge to `main`** on C2gl/tududi_addon — HA sees the new version in `config.yaml` and shows "Update available". But the Docker image doesn't exist yet, so clicking Update will 404.

2. **Run the builder workflow** — Actions → "🏗️📢 Build and Publish Add-on" → Run workflow → select `dev` or `stable` or `both`. This pushes the image to GHCR. Only then can users download the update.

**Always run the builder immediately after merging.**

The builder uses `home-assistant/builder@master` which is **deprecated** — migration to new reusable actions is pending.

## Addon Versioning

The addon version in `config.yaml` tracks the upstream tududi version. For addon-level improvements without an upstream bump, use a patch (e.g. `0.89.0` → `0.89.1`).

## Completed Work

### PR #70 — Dev addon improvements (✅ Merged, published)
- Version bump: `v0.88.5-rc.1` → `0.89.0`
- Session secret auto-generation (umask 077, persist, validate)
- Simplified Dockerfile (60+ sed → 4, with TODO for PR #946 removal)
- Port option hidden from UI
- Published to `ghcr.io/c2gl/tududi-addon-dev:0.89.0`

### PR #71 — Production addon improvements (✅ Merged)
- Same improvements as PR #70, targeting `tududi-addon/` (production)
- Version `0.89.1` (addon-level patch, still wraps tududi v0.89.0)
- Published to `ghcr.io/c2gl/tududi-addon:0.89.1`

### chrisvel/tududi#946 — Logo path fix (✅ Merged)
- Included in v1.0.0-dev.1 release. Logo sed workaround can now be removed when bumping to this version.

## Pending Minor Fixes (follow-up, apply to both addons)

From Copilot reviews on PR #70 and #71. Not blocking, can be done in a single follow-up commit:

1. **Comment mismatch in run.sh**: The comment `# Validate persisted secret (same checks as manual secret above)` is inaccurate — the persisted path also does a hex-format check that the manual path doesn't. Either update the comment or add the hex check to the manual path too.

2. **Silent chmod failure**: `chmod 600 "$SECRET_FILE" 2>/dev/null || true` silently swallows errors. Could log a warning instead.

## Planned Roadmap

1. ~~PR #70~~ → ✅ Done.
2. ~~PR #71~~ → ✅ Done.
3. **Bump dev to `1.0.0-dev.1`** → Includes logo fix (#946), so logo sed can be removed entirely (zero sed!). Keep dev ahead of production.
4. **Migrate builder workflow** → Replace deprecated `home-assistant/builder@master`.
5. **Minor fixes follow-up** → Address comment mismatch + silent chmod across both addons.

## Open Items

- Bump dev to `1.0.0-dev.1` (branch ready to create after fork sync)
- Migrate builder workflow to new HA reusable actions
- Minor fixes follow-up (comment mismatch, silent chmod)
