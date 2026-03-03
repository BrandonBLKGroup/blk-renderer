"""
BLK Group PSD-based graphic renderer.
Takes listing data + photo URLs, renders pixel-perfect graphic from PSD template.
"""
from psd_tools import PSDImage
from PIL import Image, ImageDraw, ImageFont
import io, os, requests

TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/app/templates')
PSD_PATH = os.path.join(TEMPLATE_DIR, 'BLK_Group_-_LPT_-_Social_Media_-_TEMPLATE.psd')
ANTRO_PATH = os.path.join(TEMPLATE_DIR, 'Antro_Vectra.otf')
OUTFIT_300_PATH = os.path.join(TEMPLATE_DIR, 'Outfit-Light.ttf')
OUTFIT_700_PATH = os.path.join(TEMPLATE_DIR, 'Outfit-Bold.ttf')

# Fallback system fonts
FALLBACK_LIGHT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf'
FALLBACK_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def load_font(path, fallback, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        try:
            return ImageFont.truetype(fallback, size)
        except:
            return ImageFont.load_default()

def download_photo(url):
    """Download photo from URL and return PIL Image"""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert('RGB')
    except Exception as e:
        print(f"[BLK] Photo download failed: {e}")
        # Return a gray placeholder
        return Image.new('RGB', (800, 600), (200, 200, 200))

def render_blk_graphic(listing, photo_urls, graphic_type='Just Listed!'):
    """
    Render a BLK Group graphic from PSD template.
    
    Args:
        listing: dict with street, city, state, beds, baths, sqft, price
        photo_urls: list of 1-4 photo URLs
        graphic_type: 'Just Listed!', 'Price Change!', 'Under Contract', 'Sold!'
    
    Returns:
        PNG bytes
    """
    print(f"[BLK] Rendering: {listing.get('street', '?')} - {graphic_type}")
    
    # 1. Render PSD composite
    psd = PSDImage.open(PSD_PATH)
    canvas = psd.composite().convert('RGB')
    
    # 2. Save LPT logo block BEFORE white-out
    lpt_logo = canvas.crop((700, 415, 1200, 680))
    
    # 3. Save BLK circle and MAKEARKANSASHOME area (bottom section stays)
    # We only white-out the photo grid and text replacement areas
    
    # 4. White-out photo grid (y:130 to y:935)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 130, 1200, 935], fill=(255, 255, 255))
    
    # 5. Download and place photos
    photos = []
    for url in photo_urls[:4]:
        photos.append(download_photo(url))
    
    # Pad with duplicates if less than 4
    while len(photos) < 4:
        photos.append(photos[0] if photos else Image.new('RGB', (800, 600), (200, 200, 200)))
    
    # Photo grid slots:
    # top-left hero: (0, 160) 670x400
    # top-right: (710, 160) 490x245
    # bottom-left: (0, 568) 670x340
    # bottom-right: (710, 690) 490x230
    
    p1 = photos[0].resize((670, 400), Image.LANCZOS)
    canvas.paste(p1, (0, 160))
    
    p2 = photos[1].resize((490, 245), Image.LANCZOS)
    canvas.paste(p2, (710, 160))
    
    p3 = photos[2].resize((670, 340), Image.LANCZOS)
    canvas.paste(p3, (0, 568))
    
    p4 = photos[3].resize((490, 230), Image.LANCZOS)
    canvas.paste(p4, (710, 690))
    
    # 6. Paste LPT logo back over the photo grid
    canvas.paste(lpt_logo, (700, 415))
    
    # 7. Draw white dividers
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([670, 130, 710, 935], fill=(255, 255, 255))  # vertical
    draw.rectangle([0, 558, 670, 570], fill=(255, 255, 255))     # horizontal
    
    # 8. White-out text replacement areas
    draw.rectangle([0, 75, 670, 130], fill=(255, 255, 255))   # specs text
    draw.rectangle([0, 935, 850, 1200], fill=(255, 255, 255)) # address area
    
    # 9. Load fonts
    antro = load_font(ANTRO_PATH, ANTRO_PATH, 75)
    spec_font = load_font(OUTFIT_300_PATH, FALLBACK_LIGHT, 14)
    addr_font = load_font(OUTFIT_700_PATH, FALLBACK_BOLD, 68)
    city_font = load_font(OUTFIT_300_PATH, FALLBACK_LIGHT, 28)
    
    # 10. Draw graphic type (AntroVectra, top-right)
    gt = graphic_type
    gt_bb = draw.textbbox((0, 0), gt, font=antro)
    gt_w = gt_bb[2] - gt_bb[0]
    # Center in top-right zone (center around x=938)
    draw.text((938 - gt_w // 2, 30), gt, fill=(17, 17, 17), font=antro)
    
    # 11. Draw specs
    beds = listing.get('beds', '—')
    baths = listing.get('baths', '—')
    sqft = listing.get('sqft', 0)
    price = listing.get('price', 0)
    
    spec_color = (80, 80, 80)
    draw.text((27, 83), f"{beds}  B E D R O O M S", fill=spec_color, font=spec_font)
    draw.text((137, 109), f"{baths}  B A T H R O O M S", fill=spec_color, font=spec_font)
    draw.text((281, 83), f"{sqft:,}  S Q U A R E  F E E T", fill=spec_color, font=spec_font)
    draw.text((451, 109), f"${price:,}  D O L L A R S", fill=spec_color, font=spec_font)
    
    # 12. Draw address
    street = listing.get('street', '')
    draw.text((45, 1005), street, fill=(17, 17, 17), font=addr_font)
    
    # City centered
    city = listing.get('city', '')
    state = listing.get('state', 'AR')
    city_text = f"{city.upper()},  {state.upper()}"
    city_bb = draw.textbbox((0, 0), city_text, font=city_font)
    city_w = city_bb[2] - city_bb[0]
    draw.text((600 - city_w // 2, 1090), city_text, fill=(100, 100, 100), font=city_font)
    
    # 13. Export as PNG bytes
    buf = io.BytesIO()
    canvas.save(buf, format='PNG', quality=95)
    buf.seek(0)
    
    print(f"[BLK] Render complete: {len(buf.getvalue())} bytes")
    return buf.getvalue()


if __name__ == '__main__':
    # Test render
    test_listing = {
        'street': '8 Finchley Lane',
        'city': 'Bella Vista',
        'state': 'AR',
        'beds': 3,
        'baths': 2,
        'sqft': 1850,
        'price': 325000,
    }
    png = render_blk_graphic(test_listing, [], 'Just Listed!')
    with open('/tmp/test_blk.png', 'wb') as f:
        f.write(png)
    print("Test saved to /tmp/test_blk.png")
