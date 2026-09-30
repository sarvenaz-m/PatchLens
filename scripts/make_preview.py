"""Convert the actual browser recording into a compact repository preview."""
from pathlib import Path
import shutil
import subprocess


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg is required to create the animated preview.")
    assets = Path(__file__).resolve().parents[1] / "docs" / "assets"
    source = assets / "workbench-tour.webm"
    destination = assets / "workbench-preview.gif"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", "0.5", "-i", str(source), "-t", "20.6",
            "-filter_complex_threads", "1",
            "-filter_complex",
            "fps=4,scale=960:-2:flags=lanczos,split[a][b];"
            "[a]palettegen=stats_mode=diff:max_colors=128[p];"
            "[b][p]paletteuse=dither=none:diff_mode=rectangle",
            "-loop", "0", str(destination),
        ],
        check=True,
    )
    print(f"Recorded preview: {destination} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
