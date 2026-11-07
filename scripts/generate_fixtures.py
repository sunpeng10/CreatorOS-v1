"""Generate a four-second labeled clip and a small image for local acceptance."""
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw


def main():
    target = Path(__file__).resolve().parents[1] / 'data' / 'test-fixtures'
    target.mkdir(parents=True, exist_ok=True)
    for index, color in enumerate(('#0e463e', '#284783')):
        frame = Image.new('RGB', (480, 270), color)
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((28, 34, 452, 234), radius=15, outline='white', width=3)
        draw.text((55, 94), f'TEST / CREATOROS\nSCENE 0{index + 1}\nLOCAL ACCEPTANCE FIXTURE', fill='white', spacing=9)
        frame.save(target / f'test-scene-{index + 1}.png')
    args = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y']
    for index in (1, 2):
        args.extend(['-loop', '1', '-t', '2', '-i', str(target / f'test-scene-{index}.png')])
    args.extend(['-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target / 'TEST-creatoros.mp4')])
    subprocess.run(args, check=True, timeout=30)
    print(target)


if __name__ == '__main__':
    main()
