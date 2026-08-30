"""生成与站点设计系统一致的 Windows 应用图标。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SIZE = 256
PAPER = '#F5F0E7'
INDIGO = '#303B67'
VERMILION = '#C4553E'


def _font(size: int, bold: bool = False):
    names = [
        'C:/Windows/Fonts/georgiab.ttf' if bold else 'C:/Windows/Fonts/georgia.ttf',
        'C:/Windows/Fonts/timesbd.ttf' if bold else 'C:/Windows/Fonts/times.ttf',
    ]
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def main():
    image = Image.new('RGBA', (SIZE, SIZE), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 238, 238), radius=28, fill=INDIGO)
    draw.rectangle((194, 18, 211, 83), fill=VERMILION)
    draw.line((46, 70, 121, 70), fill=VERMILION, width=5)
    draw.text((44, 38), 'CET', font=_font(27, True), fill=PAPER)
    draw.text((41, 93), 'A', font=_font(108, True), fill=PAPER)
    draw.line((48, 211, 188, 211), fill=PAPER, width=3)
    draw.line((48, 222, 151, 222), fill=VERMILION, width=5)

    output = Path(__file__).resolve().parent / 'src-tauri' / 'icons' / 'icon.ico'
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(output)


if __name__ == '__main__':
    main()
