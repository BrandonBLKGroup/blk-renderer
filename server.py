"""
BLK Renderer - Flask service for PSD-based graphic rendering.
Deployed alongside Slate Engine on Railway.
"""
from flask import Flask, request, jsonify
from render import render_blk_graphic
from supabase import create_client
import os, io

app = Flask(__name__)

SUPA_URL = os.environ.get('SUPA_URL', 'https://jdztwoaaissvauuyodfb.supabase.co')
SUPA_SERVICE_KEY = os.environ.get('SUPA_SERVICE_KEY', '')
sb = create_client(SUPA_URL, SUPA_SERVICE_KEY) if SUPA_SERVICE_KEY else None

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'service': 'BLK Renderer', 'status': 'running'})

@app.route('/render', methods=['POST'])
def render():
    """
    Render a BLK graphic.
    Body: { graphic_id: string }
    Fetches listing/photos from Supabase, renders, uploads result.
    """
    data = request.json or {}
    graphic_id = data.get('graphic_id')
    
    if not graphic_id:
        return jsonify({'error': 'graphic_id required'}), 400
    
    try:
        # 1. Get graphic record
        result = sb.table('graphics').select('*').eq('id', graphic_id).single().execute()
        graphic = result.data
        if not graphic:
            return jsonify({'error': 'Graphic not found'}), 404
        
        # 2. Get listing
        result = sb.table('listings').select('*').eq('id', graphic['listing_id']).single().execute()
        listing = result.data
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        # 3. Get client
        result = sb.table('clients').select('*').eq('id', graphic['client_id']).single().execute()
        client = result.data
        
        # 4. Get photos
        result = sb.table('listing_photos').select('*').eq('listing_id', listing['id']).order('photo_order').execute()
        photo_urls = [row['photo_url'] for row in (result.data or []) if row.get('photo_url')]
        
        print(f"[BLK] Listing: {listing.get('street')}, Photos: {len(photo_urls)}")
        
        # 5. Determine graphic type
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
        
        # 7. Upload to Supabase Storage
        filename = f"{graphic['client_id']}/graphics/{graphic_id}.png"
        sb.storage.from_('listing-photos').upload(
            filename, png_bytes,
            file_options={'content-type': 'image/png', 'upsert': 'true'}
        )
        
        file_url = f"{SUPA_URL}/storage/v1/object/public/listing-photos/{filename}"
        
        # 8. Update graphic record
        sb.table('graphics').update({
            'file_url': file_url,
            'status': 'ready'
        }).eq('id', graphic_id).execute()
        
        print(f"[BLK] Done! {file_url}")
        return jsonify({'success': True, 'file_url': file_url})
        
    except Exception as e:
        print(f"[BLK] Error: {e}")
        # Mark as failed
        if sb and graphic_id:
            try:
                sb.table('graphics').update({'status': 'failed'}).eq('id', graphic_id).execute()
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Supabase webhook for new graphics"""
    data = request.json or {}
    record = data.get('record', {})
    table = data.get('table', '')
    
    if table == 'graphics' and record.get('id'):
        graphic_id = record['id']
        print(f"[WEBHOOK] New graphic: {graphic_id}")
        # Render inline
        with app.test_request_context(json={'graphic_id': graphic_id}):
            return render()
    
    return jsonify({'ok': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
