"""
BLK Renderer - Flask service for PSD-based graphic rendering.
Uses requests instead of supabase library to avoid dependency issues.
"""
from flask import Flask, request, jsonify
from render import render_blk_graphic
import os, requests

app = Flask(__name__)

SUPA_URL = os.environ.get('SUPA_URL', '')
SUPA_SERVICE_KEY = os.environ.get('SUPA_SERVICE_KEY', '')
HEADERS = {
    'apikey': SUPA_SERVICE_KEY,
    'Authorization': f'Bearer {SUPA_SERVICE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

def supa_get(table, params=None):
    r = requests.get(f'{SUPA_URL}/rest/v1/{table}', headers=HEADERS, params=params or {})
    r.raise_for_status()
    return r.json()

def supa_update(table, match, data):
    h = {**HEADERS}
    r = requests.patch(f'{SUPA_URL}/rest/v1/{table}', headers=h, params=match, json=data)
    r.raise_for_status()
    return r.json()

def supa_upload(bucket, path, file_bytes, content_type='image/png'):
    h = {
        'apikey': SUPA_SERVICE_KEY,
        'Authorization': f'Bearer {SUPA_SERVICE_KEY}',
        'Content-Type': content_type,
        'x-upsert': 'true'
    }
    r = requests.post(f'{SUPA_URL}/storage/v1/object/{bucket}/{path}', headers=h, data=file_bytes)
    r.raise_for_status()
    return r.json()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'service': 'BLK Renderer', 'status': 'running'})

@app.route('/render', methods=['POST'])
def render():
    data = request.json or {}
    graphic_id = data.get('graphic_id')
    if not graphic_id:
        return jsonify({'error': 'graphic_id required'}), 400

    try:
        # 1. Get graphic
        graphics = supa_get('graphics', {'id': f'eq.{graphic_id}', 'select': '*'})
        if not graphics:
            return jsonify({'error': 'Graphic not found'}), 404
        graphic = graphics[0]

        # 2. Get listing
        listings = supa_get('listings', {'id': f'eq.{graphic["listing_id"]}', 'select': '*'})
        if not listings:
            return jsonify({'error': 'Listing not found'}), 404
        listing = listings[0]

        # 3. Get client
        clients = supa_get('clients', {'id': f'eq.{graphic["client_id"]}', 'select': '*'})
        client = clients[0] if clients else {}

        # 4. Get photos
        photos_data = supa_get('listing_photos', {
            'listing_id': f'eq.{listing["id"]}',
            'select': '*',
            'order': 'photo_order.asc'
        })
        photo_urls = [row['photo_url'] for row in (photos_data or []) if row.get('photo_url')]

        print(f'[BLK] Listing: {listing.get("street")}, Photos: {len(photo_urls)}')

        # 5. Graphic type
        gt_map = {
            'just_listed': 'Just Listed!',
            'price_change': 'Price Change!',
            'under_contract': 'Under Contract',
            'sold': 'Sold!',
        }
        graphic_type = gt_map.get(graphic.get('graphic_type', 'just_listed'), 'Just Listed!')

        # 6. Render
        listing_data = {
            'street': listing.get('street', ''),
            'city': listing.get('city', ''),
            'state': listing.get('state', 'AR'),
            'beds': listing.get('beds', 0),
            'baths': listing.get('baths', 0),
            'sqft': listing.get('sqft', 0),
            'price': listing.get('price', 0),
        }
        png_bytes = render_blk_graphic(listing_data, photo_urls, graphic_type)

        # 7. Upload
        filename = f'{graphic["client_id"]}/graphics/{graphic_id}.png'
        supa_upload('listing-photos', filename, png_bytes)
        file_url = f'{SUPA_URL}/storage/v1/object/public/listing-photos/{filename}'

        # 8. Update status
        supa_update('graphics', {'id': f'eq.{graphic_id}'}, {'file_url': file_url, 'status': 'ready'})

        print(f'[BLK] Done! {file_url}')
        return jsonify({'success': True, 'file_url': file_url})

    except Exception as e:
        print(f'[BLK] Error: {e}')
        try:
            supa_update('graphics', {'id': f'eq.{graphic_id}'}, {'status': 'failed'})
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json or {}
    record = data.get('record', {})
    table = data.get('table', '')
    if table == 'graphics' and record.get('id'):
        print(f'[WEBHOOK] New graphic: {record["id"]}')
        with app.test_request_context(json={'graphic_id': record['id']}):
            return render()
    return jsonify({'ok': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
