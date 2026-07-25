#!/usr/bin/env python3


import os
import logging
import json
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_environment():
    logging.info("=== CHECKING ENVIRONMENT ===")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    logging.info(f"TELEGRAM_BOT_TOKEN: {'Set' if bot_token else 'Not set'}")
    logging.info(f"TELEGRAM_CHANNEL_ID: {'Set' if channel_id else 'Not set'}")
    
    required_files = [
        'run_daily_monitor.py',
        'hotspot_notification.py',
        'broadcast_notification.py',
        'KK_PAPUA_SELATAN.geojson'
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            logging.info(f"✅ {file}: {size} bytes")
        else:
            logging.warning(f"❌ {file}: Not found")
            missing_files.append(file)
    
    return bot_token, channel_id, missing_files

def run_hotspot_monitor():
    logging.info("=== HOTSPOT MONITOR FUNCTION STARTED ===")
    logging.info(f"Timestamp: {datetime.now(ZoneInfo('Asia/Jakarta'))}")
    
    try:
        bot_token, channel_id, missing_files = check_environment()

        if not bot_token or not channel_id:
            error_msg = "Variabel lingkungan TELEGRAM_BOT_TOKEN atau TELEGRAM_CHANNEL_ID belum diatur."
            logging.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg,
                'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
            }
        
        if missing_files:
            error_msg = f"File-file penting tidak ditemukan: {', '.join(missing_files)}"
            logging.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg,
                'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
            }
        
        try:
            from run_daily_monitor import run_daily_check
            logging.info("✅ run_daily_check imported successfully")
        except Exception as e:
            logging.error(f"❌ Error importing run_daily_check: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': f'Import error: {str(e)}',
                'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
            }
        
        run_daily_check()
        
        logging.info("=== HOTSPOT MONITOR FUNCTION COMPLETED ===")
        
        return {
            'status': 'success',
            'message': 'Hotspot monitoring completed successfully using run_daily_monitor.py',
            'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error in hotspot monitor: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            'status': 'error',
            'message': f'Error: {str(e)}',
            'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
        }

@app.route('/', methods=['GET', 'POST'])
def hotspot_monitor():

    result = run_hotspot_monitor()
    if result.get('status') == 'error':
        return jsonify(result), 500
        
    return jsonify(result), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
    })

@app.route('/debug', methods=['GET'])
def debug_info():
    bot_token, channel_id, missing_files = check_environment()
    
    return jsonify({
        'bot_token_set': bool(bot_token),
        'channel_id_set': bool(channel_id),
        'missing_files': missing_files,
        'timestamp': datetime.now(ZoneInfo('Asia/Jakarta')).isoformat()
    })

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/hotspots')
def api_hotspots():
    try:
        from hotspot_notification import HotspotMonitor
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        days = request.args.get('days', 1, type=int)
        
        monitor = HotspotMonitor()
        
        if start_date and end_date:
            hotspots = monitor.get_hotspot_data(start_date=start_date, end_date=end_date)
        else:
            hotspots = monitor.get_hotspot_data(days_back=days)
        
        for feature in hotspots:
            coords = feature.get('geometry', {}).get('coordinates', [])
            props = feature.setdefault('properties', {})
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                is_in_area, area_name = monitor.is_hotspot_in_conservation_area(lat, lon)
                props['_in_conservation_area'] = is_in_area
                props['_conservation_area_name'] = area_name

                if not is_in_area:
                    is_near, near_area, dist_m = monitor.is_hotspot_near_conservation_area(lat, lon)
                    props['_near_conservation_area'] = is_near
                    props['_near_boundary_area_name'] = near_area
                    props['_near_boundary_distance_m'] = dist_m
                else:
                    props['_near_conservation_area'] = False
                    props['_near_boundary_area_name'] = None
                    props['_near_boundary_distance_m'] = None
        
        return jsonify({
            'type': 'FeatureCollection',
            'features': hotspots
        })
    except Exception as e:
        logging.error(f"Error in api_hotspots: {e}")
        return jsonify({'type': 'FeatureCollection', 'features': [], 'error': str(e)}), 500

@app.route('/api/conservation-areas')
def api_conservation_areas():
    try:
        import geopandas as gpd
        
        geojson_path = 'KK_PAPUA_SELATAN.geojson'
        if not os.path.exists(geojson_path):
            return jsonify({'type': 'FeatureCollection', 'features': [], 'error': 'GeoJSON file not found'}), 404
        
        gdf = gpd.read_file(geojson_path)
        geojson_data = json.loads(gdf.to_json())
        
        return jsonify(geojson_data)
    except Exception as e:
        logging.error(f"Error in api_conservation_areas: {e}")
        return jsonify({'type': 'FeatureCollection', 'features': [], 'error': str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 
