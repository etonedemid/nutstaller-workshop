# NutStaller Workshop

Community blueprints (vehicles) and reNut part mods for Banjo-Kazooie: Nuts & Bolts, browsed and installed from [NutStaller](https://github.com/etonedemid/NutStaller)'s Workshop page.

## Sharing a blueprint

In NutStaller open **Workshop**, then the **Share** tab. Pick the vehicle from your save, give it a name, a short description and a screenshot, then press **Copy and open GitHub**. Paste into the issue form and submit. A bot validates and publishes it, usually within a minute (submissions wait while the bot is offline).

Rules the bot enforces:
- At most 3 blueprints per 10 minutes per account.
- A real blueprint file and a JPEG or PNG preview (NutStaller prepares both).

## Sharing a part mod

reNut loads custom vehicle parts from `.nbpatch` mods (see reNut's [custom-parts.md](https://github.com/masterspike52/reNut/blob/main/docs/modding/custom-parts.md)). In NutStaller open **Workshop**, **Share**, then **Part mod**: pick the `.nbpatch`, a name, description and screenshot, and press **Copy and open GitHub**. Paste into the form and drag in the `.nbpatch.zip` NutStaller puts in the folder it opens.

- Only part mods: part files and the mod's own new bundles. Mods that change game files or patch the executable are refused.
- At most 25 MB, 3 submissions per 10 minutes.
- The bot checks the file and moderates the text and screenshot, then labels the issue `checked`. Models and textures can't be checked automatically, so a maintainer adds `approved` before it is published. An approval counts only for the file that was checked.
- A newer version from the same author (same mod Id) replaces the old one.

## Dependencies

Every part in a blueprint is stored as its asset id, and a custom part's is reNut's `AssetId("banjox_vehicleblock_renut_<part id>")`. The bot works out which hosted mods each blueprint needs (`requires` in `index.json`) from the blueprint itself. Custom parts from mods that are not in the workshop are listed as `missing`, with the mod's name. NutStaller downloads the required mods together with the vehicle.

## Layout

- `blueprints/<id>/blueprint.bin`: the vehicle, exactly as the game saves it.
- `blueprints/<id>/preview.jpg`: the screenshot.
- `blueprints/<id>/meta.json`: name, description, author (the submitter's GitHub login), part count, date.
- `mods/<id>/meta.json` and `preview.jpg`: a part mod. The `.nbpatch` itself is the asset of the release `mod-<id>`.
- `index.json`: every blueprint and mod, rebuilt by `tools/workshop.py`. NutStaller reads this file.

Maintainers remove a blueprint by deleting its folder; the bot rebuilds the index on its next pass.

## The bot

It runs on a maintainer's PC rather than GitHub Actions: `tools/workshop.py bot` checks the open `blueprint` issues every minute, publishes the valid ones, pushes, then replies and closes each issue. It uses `gh auth token` and the git login of whoever runs it, in its own clone:

```
git clone https://github.com/etonedemid/nutstaller-workshop ~/.local/share/nutstaller-workshop-bot
python3 -I ~/.local/share/nutstaller-workshop-bot/tools/workshop.py bot
```

`tools/nutstaller-workshop-bot.service` runs it as a systemd user service.

## Moderation

Before anything is published, the bot shows the preview, name and description to a local vision model (aiden-llm on `127.0.0.1:8788`, override with `WORKSHOP_LLM`):

- Harmful (sexual content, anything sexual involving minors, gore, hate or harassment, personal information, spam): the issue is deleted and nothing is saved. One line goes to `~/.local/share/nutstaller-workshop-moderation.log` (issue, author, reason).
- Off topic (not from the game): rejected with a reply.
- Model not running: the issue waits for the next pass. Nothing is published unmoderated.

If something gets through anyway, `tools/workshop.py purge <id>` erases that blueprint from the whole git history and force-pushes. Other clones then need `git fetch && git reset --hard origin/main`. GitHub can still serve old objects by hash for a while, so for illegal content also report it to GitHub Support (for CSAM GitHub handles the report to NCMEC). A model is not a reliable CSAM detector; it is a first filter, not a guarantee.

## Blueprint format

Big-endian. It starts with the magic `3F9AE148 40547AE1`. A u16 part count sits at 0x08 and the vehicle name at 0x28 (32 UTF-16 characters). The 0x84-byte header is followed by one 36-byte record per part (part type hash, grid position, rotation, RGBA color). In the save, each vehicle is a save-game content package named `0x%08x`, with display name `VEHICLE: <name>`.
