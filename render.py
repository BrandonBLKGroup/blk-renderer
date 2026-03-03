"""
BLK Group graphic renderer.
Uses pre-rendered PSD composite (PNG) + PIL. No psd-tools needed at runtime.
"""
from PIL import Image, ImageDraw, ImageFont
import io, os, requests

TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/app/templates')

# Find base composite PNG
BASE_PATH = None
for f in os.listdir(TEMPLATE_DIR) if os.path.isdir(TEMPLATE_DIR) else []:
    if f.lower().endswith('.png') and 'composite' in f.lower():
        BASE_PATH = os.path.join(TEMPLATE_DIR, f)
        break
if not BASE_PATH:
    BASE_PATH = os.path.join(TEMPLATE_DIR, 'blk_base_composite.png')

# Find font file
ANTRO_PATH = None
for f in os.listdir(TEMPLATE_DIR) if os.path.isdir(TEMPLATE_DIR) else []:
    if 'antro' in f.lower() or 'vectra' in f.lower():
        ANTRO_PATH = os.path.join(TEMPLATE_DIR, f)
        break
if not ANTRO_PATH:
    ANTRO_PATH = os.path.join(TEMPLATE_DIR, 'Antro_Vectra.otf')

FALLBACK_LIGHT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf'
FALLBACK_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

print(f"[BLK] BASE_PATH: {BASE_PATH} (exists: {os.path.exists(BASE_PATH)})")
print(f"[BLK] ANTRO_PATH: {ANTRO_PATH} (exists: {os.path.exists(ANTRO_PATH)})")
print(f"[BLK] Templates dir: {os.listdir(TEMPLATE_DIR) if os.path.isdir(TEMPLATE_DIR) else 'NOT FOUND'}")

def load_font(path, fallback, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        try:
            return ImageFont.truetype(fallback, size)
        except:
            return ImageFont.load_default()

def download_photo(url):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert('RGB')
    except Exception as e:
        print(f"[BLK] Photo download failed: {e}")
        return Image.new('RGB', (800, 600), (200, 200, 200))

def render_blk_graphic(listing, photo_urls, graphic_type='Just Listed!'):
    print(f"[BLK] Rendering: {listing.get('street', '?')} - {graphic_type}")

    # 1. Load pre-rendered composite
    canvas = Image.open(BASE_PATH).convert('RGB')

    # 2. Save LPT logo block BEFORE white-out
    lpt_logo = canvas.crop((700, 415, 1200, 680))

    # 3. White-out photo grid (y:130 to y:935)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 130, 1200, 935], fill=(255, 255, 255))

    # 4. Download and place photos
    photos = []
    for url in photo_urls[:4]:
        photos.append(download_photo(url))
    while len(photos) < 4:
        photos.append(photos[0] if photos else Image.new('RGB', (800, 600), (200, 200, 200)))

    p1 = photos[0].resize((670, 400), Image.LANCZOS)
    canvas.paste(p1, (0, 160))
    p2 = photos[1].resize((490, 245), Image.LANCZOS)
    canvas.paste(p2, (710, 160))
    p3 = photos[2].resize((670, 340), Image.LANCZOS)
    canvas.paste(p3, (0, 568))
    p4 = photos[3].resize((490, 230), Image.LANCZOS)
    canvas.paste(p4, (710, 690))

    # 5. Paste LPT logo back
    canvas.paste(lpt_logo, (700, 415))

    # 6. Draw white dividers
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([670, 130, 710, 935], fill=(255, 255, 255))
    draw.rectangle([0, 558, 670, 570], fill=(255, 255, 255))

    # 7. White-out text areas
    draw.rectangle([0, 75, 670, 130], fill=(255, 255, 255))
    draw.rectangle([0, 935, 850, 1200], fill=(255, 255, 255))

    # 8. Load fonts
    antro = load_font(ANTRO_PATH, ANTRO_PATH, 75)
    spec_font = load_font(FALLBACK_LIGHT, FALLBACK_LIGHT, 16)
    addr_font = load_font(FALLBACK_BOLD, FALLBACK_BOLD, 78)
    city_font = load_font(FALLBACK_LIGHT, FALLBACK_LIGHT, 28)

    # 9. Draw graphic type (AntroVectra, top-right)
    gt = graphic_type
    gt_bb = draw.textbbox((0, 0), gt, font=antro)
    gt_w = gt_bb[2] - gt_bb[0]
    draw.text((938 - gt_w // 2, 30), gt, fill=(17, 17, 17), font=antro)

    # 10. Draw specs
    beds = listing.get('beds', 0)
    baths = listing.get('baths', 0)
    sqft = listing.get('sqft', 0)
    price = listing.get('price', 0)
    spec_color = (80, 80, 80)
    draw.text((27, 83), f"{beds}  B E D R O O M S", fill=spec_color, font=spec_font)
    draw.text((180, 109), f"{baths}  B A T H R O O M S", fill=spec_color, font=spec_font)
    draw.text((340, 83), f"{sqft:,}  S Q U A R E  F E E T", fill=spec_color, font=spec_font)
    draw.text((540, 109), f"${price:,}  D O L L A R S", fill=spec_color, font=spec_font)

    # 11. Draw address - large bold
    street = listing.get('street', '')
    draw.text((35, 990), street, fill=(17, 17, 17), font=addr_font)

    # City centered below address
    city = listing.get('city', '')
    state = listing.get('state', 'AR')
    city_text = f"{city.upper()},  {state.upper()}"
    city_bb = draw.textbbox((0, 0), city_text, font=city_font)
    city_w = city_bb[2] - city_bb[0]
    draw.text((400 - city_w // 2, 1080), city_text, fill=(100, 100, 100), font=city_font)

    # 12. Export
    buf = io.BytesIO()
    canvas.save(buf, format='PNG', quality=95)
    buf.seek(0)
    print(f"[BLK] Render complete: {len(buf.getvalue())} bytes")
    return buf.getvalue()
