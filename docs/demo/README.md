# Demo assets

`tiro-demo.gif` (README hero), `tiro-demo.mp4` and the three `tiro-*.png`
screenshots are browser recordings of the real Next.js UI running in replay mode
(`DEMO_REPLAY=true`). Replay serves two real recorded runs (Harbor Desk exports and
the grooming-salon call) with the pipeline's timing; nothing is generated or mocked
by hand. The approved stories become dry-run previews.

Recreate from `apps/web`:

```powershell
$env:DEMO_REPLAY = "true"; npm.cmd run build
node node_modules/next/dist/bin/next start --port 3008   # second terminal
node scripts/record-demo.mjs http://127.0.0.1:3008 ../../docs/demo
```

The script records `tiro-demo.webm` and the screenshots; convert with ffmpeg:

```powershell
ffmpeg -ss 1 -i ../../docs/demo/tiro-demo.webm -vf "fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" ../../docs/demo/tiro-demo.gif
ffmpeg -i ../../docs/demo/tiro-demo.webm -c:v libx264 -pix_fmt yuv420p -crf 24 -movflags +faststart -an ../../docs/demo/tiro-demo.mp4
```

`scripts/capture-demo.mjs` captures the same flow against the real local
FastAPI/Neon backend for an existing run; it refuses anything but local dry-run.
