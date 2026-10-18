#!/usr/bin/env python3
"""Mechanical tududi version bump for C2gl/tududi_addon.

  plan  --repo DIR [--scope auto|dev|stable]       -> plan.json + GitHub outputs
  apply --repo DIR                                  -> edit Dockerfile, config.yaml, CHANGELOG.md
  body  [--closes N]                                -> PR body (markdown) on stdout

Rules (scope=auto): the dev addon follows the newest upstream tag (pre-releases
included); the stable addon follows the newest non-pre-release tag.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

APP_REPO = os.environ.get("APP_REPO", "chrisvel/tududi")
ADDONS = {"dev": "tududi-addon-dev", "stable": "tududi-addon"}
PLAN_FILE = os.environ.get("PLAN_FILE", "plan.json")

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
CLONE_RE = re.compile(r"(--branch\s+)(v\S+)(\s+https://github\.com/chrisvel/tududi)")
VERSION_RE = re.compile(r'^(version:\s*)"?([^"\n]+)"?\s*$', re.M)
DESC_VER_RE = re.compile(r"\(v\d[^)]*\)")


def die(msg):
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(1)


def semver_key(tag):
    """SemVer 2.0 precedence key, or None for tags that are not vX.Y.Z[-pre]."""
    m = TAG_RE.match(tag)
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    if pre is None:
        return (int(major), int(minor), int(patch), 1, ())
    ids = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (int(major), int(minor), int(patch), 0, ids)


def is_pre(tag):
    return semver_key(tag)[3] == 0


def upstream_tags():
    out = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", f"https://github.com/{APP_REPO}.git"],
        check=True, capture_output=True, text=True).stdout
    tags = [line.split("refs/tags/", 1)[1] for line in out.splitlines() if "refs/tags/" in line]
    return sorted((t for t in tags if semver_key(t)), key=semver_key)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def current(repo, addon):
    d = os.path.join(repo, ADDONS[addon])
    m = CLONE_RE.search(read(os.path.join(d, "Dockerfile")))
    v = VERSION_RE.search(read(os.path.join(d, "config.yaml")))
    if not m or not v:
        die(f"could not read the pinned tag/version of {ADDONS[addon]}")
    return m.group(2), v.group(2).strip()


def version_gt(new, old):
    """HA Supervisor compares add-on versions with awesomeversion; use it when available."""
    try:
        from awesomeversion import AwesomeVersion
        return AwesomeVersion(new) > AwesomeVersion(old)
    except ImportError:
        return True


def cmd_plan(args):
    tags = upstream_tags()
    latest = tags[-1]
    latest_stable = [t for t in tags if not is_pre(t)][-1]
    wanted = {"dev": latest, "stable": latest_stable}
    scope = ("dev", "stable") if args.scope == "auto" else (args.scope,)

    plan = {}
    for addon in scope:
        tag_from, ver_from = current(args.repo, addon)
        tag_to = wanted[addon]
        if semver_key(tag_from) is None or semver_key(tag_to) <= semver_key(tag_from):
            continue
        ver_to = tag_to[1:]
        if not version_gt(ver_to, ver_from):
            die(f"{ADDONS[addon]}: {ver_to} is not newer than {ver_from} for Home Assistant")
        plan[addon] = {"from": tag_from, "to": tag_to, "version_from": ver_from, "version": ver_to}

    if not plan:
        title = branch = ""
    elif set(plan) == {"dev", "stable"} and plan["dev"]["to"] == plan["stable"]["to"]:
        v = plan["dev"]["version"]
        title, branch = f"Bump dev and stable addons to tududi v{v}", f"pr/c2gl-bump-{v}"
    elif set(plan) == {"dev", "stable"}:
        d, s = plan["dev"]["version"], plan["stable"]["version"]
        title = f"Bump dev addon to tududi v{d} and stable addon to v{s}"
        branch = f"pr/c2gl-bump-dev-{d}-stable-{s}"
    elif "dev" in plan:
        v = plan["dev"]["version"]
        title, branch = f"Bump dev addon to tududi v{v}", f"pr/c2gl-bump-dev-{v}"
    else:
        v = plan["stable"]["version"]
        title, branch = f"Promote stable addon to tududi v{v}", f"pr/c2gl-promote-stable-{v}"

    write(PLAN_FILE, json.dumps({"addons": plan, "title": title, "branch": branch}, indent=2))
    print(f"needed={'true' if plan else 'false'}")
    print(f"title={title}")
    print(f"branch={branch}")
    print(f"targets={' '.join(plan)}")
    print(f"stable_version={plan.get('stable', {}).get('to', '')}")
    for addon, p in plan.items():
        print(f"{addon}: {p['from']} -> {p['to']}", file=sys.stderr)
    if not plan:
        print(f"Up to date (newest upstream: {latest}, newest stable: {latest_stable})", file=sys.stderr)


def changelog_entry(p):
    return (f"## {p['version']}\n"
            f"**BUMPED:** bumped to tududi {p['to']} (from {p['from']})\n\n"
            f"Upstream release notes: https://github.com/{APP_REPO}/releases/tag/{p['to']}\n\n")


def cmd_apply(args):
    plan = json.loads(read(PLAN_FILE))
    for addon, p in plan["addons"].items():
        d = os.path.join(args.repo, ADDONS[addon])

        path = os.path.join(d, "Dockerfile")
        text, n = CLONE_RE.subn(lambda m: m.group(1) + p["to"] + m.group(3), read(path))
        if n != 1:
            die(f"{path}: expected exactly one tududi clone line, found {n}")
        write(path, text)

        path = os.path.join(d, "config.yaml")
        text = VERSION_RE.sub(lambda m: f'{m.group(1)}"{p["version"]}"', read(path), count=1)
        # The dev description names the wrapped version, e.g. "(v1.9.3)"; stable's does not.
        text = re.sub(r'^(description:.*)$',
                      lambda m: DESC_VER_RE.sub(f"({p['to']})", m.group(1)), text, count=1, flags=re.M)
        write(path, text)

        path = os.path.join(d, "CHANGELOG.md")
        text = read(path)
        i = text.find("\n## ")
        if i < 0:
            die(f"{path}: no '## ' heading found")
        write(path, text[:i + 1] + changelog_entry(p) + text[i + 1:])


def fetch_releases():
    req = urllib.request.Request(f"https://api.github.com/repos/{APP_REPO}/releases?per_page=100",
                                 headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:  # release notes are a nice-to-have
        print(f"::warning::could not fetch release notes: {e}", file=sys.stderr)
        return []


def box(checked):
    return "x" if checked else " "


def cmd_body(args):
    plan = json.loads(read(PLAN_FILE))
    addons = plan["addons"]
    lo = min((p["from"] for p in addons.values()), key=semver_key)
    hi = max((p["to"] for p in addons.values()), key=semver_key)

    if len(addons) == 2 and addons["dev"] == addons["stable"]:
        desc = f"the dev and stable addons from tududi {lo} to {hi}"
    else:
        desc = " and ".join(f"the {a} addon from tududi {p['from']} to {p['to']}" for a, p in addons.items())
    changes = []
    for addon, p in addons.items():
        d = ADDONS[addon]
        changes += [f"- `{d}/Dockerfile`: clone tag `{p['from']}` → `{p['to']}`",
                    f"- `{d}/config.yaml`: version `{p['version_from']}` → `{p['version']}`"
                    + (", description updated" if addon == "dev" else ""),
                    f"- `{d}/CHANGELOG.md`: new `{p['version']}` entry"]

    notes, total = [], 0
    for rel in sorted(fetch_releases(), key=lambda r: semver_key(r["tag_name"]) or (0,)):
        k = semver_key(rel["tag_name"])
        if not k or not (semver_key(lo) < k <= semver_key(hi)):
            continue
        text = (rel.get("body") or "No release notes.").strip()
        if len(text) > 6000:
            text = text[:6000] + "\n\n…(truncated)"
        if total + len(text) > 40000:
            notes.append(f"…more releases: https://github.com/{APP_REPO}/releases")
            break
        total += len(text)
        notes.append(f"### {rel['tag_name']}\n{text}")

    run = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run = (f" ([run]({os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
               f"/actions/runs/{os.environ['GITHUB_RUN_ID']}))")
    builder = "both" if len(addons) == 2 else next(iter(addons))

    print(f"""## Description
Bumps {desc}. Mechanical version bump opened automatically; the addon-impact review and local verification follow before this leaves draft.

## Type of Change
<!-- Mark relevant options with an "x" -->
- [ ] Bug fix (non-breaking change which fixes an issue)
    - [ ] Referenced the bug
- [ ] New feature (non-breaking change which adds functionality)
    - [ ] was there a feature request, if yes, linked
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] CI/CD changes
- [x] Bump Dependancies

## Changes Made
<!-- List the specific changes made in this PR -->
{chr(10).join(changes)}

## Testing
<!-- Describe how you tested these changes -->
- [ ] Local testing completed
- [ ] Add-on builds successfully
- [ ] Tested in Home Assistant
- [ ] No breaking changes confirmed

## Add-on Affected
<!-- Mark which addon(s) are affected -->
- [{box('stable' in addons)}] Stable addon (`tududi-addon`)
- [{box('dev' in addons)}] Development addon (`tududi-addon-dev`)
- [ ] Repository configuration
- [ ] CI/CD workflows

## Checklist
<!-- Mark completed items with an "x" -->
- [ ] Self-review of code completed
- [ ] Changes generate no new warnings
- [ ] Documentation updated (if needed)
- [x] Changelog updated (if needed)
- [x] Version number updated (if needed)

## Screenshots (if applicable)
<!-- Add screenshots to help explain your changes -->

## Additional Notes
<!-- Any additional information that reviewers should know -->
Opened by the `upstream-bump` workflow in the fork{run}.

**Still to do before ready for review:** addon-impact review of {lo}...{hi} (upstream `Dockerfile`, `backend/cmd/start.sh`, `backend/config/config.js`, `package.json`, new migrations), local build + upgrade test, and a fuller CHANGELOG entry.

**After merge:** run the builder workflow for `{builder}`, then smoke test in HA.

Upstream diff: https://github.com/{APP_REPO}/compare/{lo}...{hi}
{f"{chr(10)}Closes #{args.closes}{chr(10)}" if args.closes else ""}
<details><summary>Upstream release notes</summary>

{chr(10).join(notes) if notes else "No GitHub releases found for this range."}

</details>""")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--repo", required=True)
    p.add_argument("--scope", default="auto", choices=["auto", "dev", "stable"])
    p = sub.add_parser("apply")
    p.add_argument("--repo", required=True)
    p = sub.add_parser("body")
    p.add_argument("--closes", default="")
    args = ap.parse_args()
    {"plan": cmd_plan, "apply": cmd_apply, "body": cmd_body}[args.cmd](args)


if __name__ == "__main__":
    main()
