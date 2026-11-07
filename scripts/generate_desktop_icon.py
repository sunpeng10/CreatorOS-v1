from pathlib import Path
from PIL import Image, ImageDraw

target = Path(__file__).resolve().parents[1] / 'apps' / 'desktop' / 'assets'
target.mkdir(parents=True, exist_ok=True)
image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((2, 2, 254, 254), radius=60, fill='#147c67')
draw.line([(99, 60), (157, 60)], fill='#f5f6da', width=13)
draw.line([(110, 62), (110, 110), (69, 181), (70, 196), (83, 202), (173, 202), (187, 196), (187, 181), (146, 110), (146, 62)], fill='#f5f6da', width=11, joint='curve')
draw.polygon([(91, 160), (165, 160), (182, 190), (75, 190)], fill='#afca87')
draw.ellipse((111, 131, 122, 142), fill='#f5f6da')
draw.ellipse((134, 173, 145, 184), fill='#147c67')
image.save(target / 'creatoros.png')
image.save(target / 'creatoros.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
