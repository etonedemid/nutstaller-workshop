#!/usr/bin/env python3
"""NutStaller workshop: publishes blueprint submissions and rebuilds index.json.

  workshop.py submit   GitHub Action on a new issue: validate the submission in
                       the issue body, publish it under blueprints/<issue>/ and
                       write the reply to reply.md (exit 0 published, 1 rejected)
  workshop.py index    rebuild index.json from blueprints/*/meta.json
  workshop.py test     self-check of the parsers

Standard library only. The issue body is untrusted: it is read from the event
file, never through a shell, and only validated bytes are written.
"""
import base64
import datetime
import json
import os
import re
import struct
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINTS = ROOT / "blueprints"

MAGIC = bytes.fromhex("3f9ae14840547ae1")  # every N&B blueprint starts with it
HEADER_SIZE = 0x84
PART_SIZE = 36
MAX_PARTS = 1000
MAX_PREVIEW = 160 * 1024
MAX_NAME = 31          # the game's name field holds 32 UTF-16 characters
MAX_DESCRIPTION = 200
RATE_LIMIT = 3         # submissions per user ...
RATE_WINDOW = datetime.timedelta(minutes=10)
MIN_ACCOUNT_AGE = datetime.timedelta(days=7)


class Rejected(Exception):
    pass


def parse_blueprint(data):
    """(name, parts) of a blueprint file, or Rejected."""
    if len(data) < HEADER_SIZE or data[:8] != MAGIC:
        raise Rejected("that is not a Nuts & Bolts blueprint")
    parts = struct.unpack(">H", data[8:10])[0]
    if not 1 <= parts <= MAX_PARTS or len(data) != HEADER_SIZE + parts * PART_SIZE:
        raise Rejected("the blueprint is damaged (its size does not match its part count)")
    name = data[0x28:0x68].decode("utf-16-be", "replace").split("\0")[0]
    return name, parts


def image_type(data):
    if data[:3] == b"\xff\xd8\xff" and data[-2:] == b"\xff\xd9":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    raise Rejected("the preview must be a JPEG or PNG image")


def clean_text(text, limit):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text)).strip()
    return re.sub(r"\s+", " ", text)[:limit]


def parse_submission(body):
    """The JSON block NutStaller puts in the issue."""
    # The form's code block (```text) around the JSON, or the bare JSON.
    match = re.search(r"(\{\s*\"name\".*\})", body or "", re.S)
    if not match:
        raise Rejected("no NutStaller submission found in the issue (paste what NutStaller copied)")
    try:
        sub = json.loads(match.group(1))
        blueprint = base64.b64decode(sub["blueprint"], validate=True)
        preview = base64.b64decode(sub["preview"], validate=True)
    except (ValueError, KeyError, TypeError):
        raise Rejected("the submission is incomplete or damaged; copy it from NutStaller again")
    name = clean_text(sub.get("name", ""), MAX_NAME)
    description = clean_text(sub.get("description", ""), MAX_DESCRIPTION)
    if not name:
        raise Rejected("the blueprint needs a name")
    if len(preview) > MAX_PREVIEW:
        raise Rejected("the preview image is too large")
    _, parts = parse_blueprint(blueprint)
    return name, description, blueprint, preview, image_type(preview), parts


def github(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "Accept": "application/vnd.github+json",
        "User-Agent": "nutstaller-workshop",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def when(stamp):
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def check_author(repo, login, now):
    """Bot protection: no brand-new accounts, at most RATE_LIMIT submissions per window."""
    user = github(f"/users/{login}")
    if user.get("type") != "User":
        raise Rejected("submissions come from people, not bots")
    if now - when(user["created_at"]) < MIN_ACCOUNT_AGE:
        raise Rejected("your GitHub account is too new to submit blueprints yet; try again in a few days")
    issues = github(f"/repos/{repo}/issues?creator={login}&state=all&labels=blueprint"
                    "&sort=created&direction=desc&per_page=20")
    recent = [i for i in issues if now - when(i["created_at"]) < RATE_WINDOW]
    if len(recent) > RATE_LIMIT:
        raise Rejected(f"only {RATE_LIMIT} blueprints per 10 minutes; wait a bit and submit again")


def rebuild_index():
    entries = []
    for meta_file in BLUEPRINTS.glob("*/meta.json"):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        folder = meta_file.parent.name
        if not (meta_file.parent / "blueprint.bin").exists():
            continue
        meta["id"] = folder
        meta["blueprint"] = f"blueprints/{folder}/blueprint.bin"
        meta["preview"] = f"blueprints/{folder}/{meta.pop('preview_file', 'preview.jpg')}"
        entries.append(meta)
    entries.sort(key=lambda m: m.get("created", ""), reverse=True)
    (ROOT / "index.json").write_text(
        json.dumps({"version": 1, "blueprints": entries}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")


def submit():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event["issue"]
    login = issue["user"]["login"]
    now = datetime.datetime.now(datetime.timezone.utc)
    reply = ROOT / "reply.md"
    try:
        check_author(os.environ["GITHUB_REPOSITORY"], login, now)
        name, description, blueprint, preview, ext, parts = parse_submission(issue.get("body"))
    except Rejected as e:
        reply.write_text(f"Not published: {e}.\n", encoding="utf-8")
        return 1
    folder = BLUEPRINTS / str(issue["number"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "blueprint.bin").write_bytes(blueprint)
    (folder / f"preview.{ext}").write_bytes(preview)
    meta = {"name": name, "description": description, "author": login, "parts": parts,
            "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "preview_file": f"preview.{ext}"}
    (folder / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    rebuild_index()
    reply.write_text(f"Published **{name}** ({parts} parts). It shows up in NutStaller's "
                     "workshop within a few minutes.\n", encoding="utf-8")
    return 0


def test():
    blueprint = MAGIC + struct.pack(">H", 2) + b"\0" * (0x28 - 10) + \
        "Car".encode("utf-16-be").ljust(64, b"\0") + b"\0" * (HEADER_SIZE - 0x68) + b"\0" * 72
    assert parse_blueprint(blueprint) == ("Car", 2)
    for bad in (blueprint[:-1], b"x" + blueprint[1:]):
        try:
            parse_blueprint(bad)
            raise AssertionError("accepted a bad blueprint")
        except Rejected:
            pass
    jpeg = b"\xff\xd8\xff\xe0" + b"\0" * 10 + b"\xff\xd9"
    body = "### Submission\n\n```text\n" + json.dumps({
        "name": "  Car\x07 ", "description": "a\nb",
        "blueprint": base64.b64encode(blueprint).decode(),
        "preview": base64.b64encode(jpeg).decode()}) + "\n```\n"
    name, description, _, _, ext, parts = parse_submission(body)
    assert (name, description, ext, parts) == ("Car", "a b", "jpg", 2), (name, description, ext)
    print("ok")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "submit":
        sys.exit(submit())
    elif mode == "index":
        rebuild_index()
    elif mode == "test":
        test()
    else:
        sys.exit(__doc__)
