# NutStaller Workshop

Community blueprints (vehicles) for Banjo-Kazooie: Nuts & Bolts, browsed and installed from [NutStaller](https://github.com/etonedemid/NutStaller)'s Workshop page.

## Sharing a blueprint

In NutStaller open **Workshop**, then **Share a blueprint**. Pick the vehicle from your save, give it a name, a short description and a screenshot, then press **Copy and open GitHub**. Paste into the issue form and submit. A bot validates and publishes it within a minute.

Rules the bot enforces:
- A GitHub account older than 7 days.
- At most 3 blueprints per 10 minutes per account.
- A real blueprint file and a JPEG or PNG preview (NutStaller prepares both).

## Layout

- `blueprints/<id>/blueprint.bin`: the vehicle, exactly as the game saves it.
- `blueprints/<id>/preview.jpg`: the screenshot.
- `blueprints/<id>/meta.json`: name, description, author (the submitter's GitHub login), part count, date.
- `index.json`: every blueprint, rebuilt by `tools/workshop.py`. NutStaller reads this file.

Maintainers remove a blueprint by deleting its folder; the index rebuilds itself.

## Blueprint format

Big-endian. It starts with the magic `3F9AE148 40547AE1`. A u16 part count sits at 0x08 and the vehicle name at 0x28 (32 UTF-16 characters). The 0x84-byte header is followed by one 36-byte record per part (part type hash, grid position, rotation, RGBA color). In the save, each vehicle is a save-game content package named `0x%08x`, with display name `VEHICLE: <name>`.
