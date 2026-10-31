# SnowRunner Time Lock

A small command-prompt tool that locks the time of day in SnowRunner (Steam, PC), so you don't have to keep changing it on the map while the daylight fades.

**Single player / offline only.** It works by writing to the running game's memory, like a trainer. Don't use it in co-op. Use at your own risk. Not affiliated with or endorsed by Saber Interactive or Focus Entertainment.

## Use it

1. Download `SnowRunnerTimeLock.exe` from the [Releases](../../releases) page.
2. Start SnowRunner and load into a map.
3. Run `SnowRunnerTimeLock.exe` (double-click; if it can't attach, right-click and choose *Run as administrator*).
4. Press **Esc** in the game to pause, then in the tool choose `1`, type the time the game shows (for example `19:42`), and the time to lock at (for example `12:00`).
5. Unpause. The time now stays put.

After loading another map, or restarting the game, use option `1` again. Choose `2` to unlock and `4` to quit.

`config.json` is created next to the exe the first time you run it.

## Game updates

The tool finds the clock through pointer paths that start inside the game's `pros.sdk.x64.dll`. A game update can change them. If option `1` can no longer find the clock after an update, the paths in `config.json` are out of date and need to be found again with Cheat Engine (pointer scan with two saved pointermaps compared, then put the new `base_offset` and `offsets` values in `config.json`). Option `3` shows what each path currently resolves to, which helps in bug reports.


Windows antivirus software sometimes flags unsigned PyInstaller exes and anything that reads another process's memory. The full source is in this repository.
