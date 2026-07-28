import requests
import json
import time
import geopandas as gpd
from shapely.geometry import Point
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv
from broadcast_notification import ChannelNotifier

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hotspot_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

DEFAULT_PROVINSI_IDS = ['39']

class HotspotMonitor:
    def __init__(self):
        self.sipongi_api_url = "https://opsroom.sipongidata.my.id/api/opsroom/indoHotspot"
        self.protected_areas = self.load_protected_areas()
        
    def load_protected_areas(self):
        try:
            if os.path.exists('KK_PAPUA_SELATAN.geojson'):
                gdf = gpd.read_file('KK_PAPUA_SELATAN.geojson')
                logging.info(f"Loaded {len(gdf)} features from KK_PAPUA_SELATAN.geojson")

                gdf_proj = gdf.to_crs("EPSG:3857")
                
                protected_areas = {}
                for idx, row in gdf.iterrows():
                    area_id = f"kawasan_konservasi_{idx+1}"
                    area_name = row.get('NAMA_KWS', row.get('name', f'Kawasan Konservasi {idx+1}'))
                    protected_areas[area_id] = {
                        'name': area_name,
                        'geometry': row.geometry,
                        'geometry_proj': gdf_proj.loc[idx].geometry 
                    }
                logging.info(f"Loaded {len(protected_areas)} kawasan konservasi (dengan proyeksi UTM untuk buffer)")
                return protected_areas
        except Exception as e:
            logging.error(f"Gagal memuat file kawasan konservasi: {e}")
            raise

        raise FileNotFoundError("KK_PAPUA_SELATAN.geojson not found. Cannot initialize HotspotMonitor.")
    
    def get_hotspot_data(self, provinsi_id=None, kabkota_id=None, days_back=1, specific_date=None, start_date=None, end_date=None):
        if start_date and end_date:
            logging.info(f"Mengambil data untuk rentang tanggal: {start_date} - {end_date}")
            time_params = {
                'filterperiode': 'true',
                'from': start_date,
                'to': end_date,
                'late': 'custom',
            }
        elif specific_date:
            logging.info(f"Mengambil data untuk tanggal spesifik: {specific_date}")
            from_date = specific_date
            to_date = (datetime.strptime(specific_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            time_params = {
                'filterperiode': 'true',
                'from': from_date,
                'to': to_date,
                'late': 'custom',
            }
        else:
            logging.info(f"Mengambil data untuk {days_back} hari terakhir.")
            hours_back = days_back * 24
            time_params = {
                'filterperiode': 'false',
                'from': '',
                'to': '',
                'late': str(hours_back),
            }
        
        if provinsi_id is None:
            provinsi_ids = DEFAULT_PROVINSI_IDS
        elif isinstance(provinsi_id, list):
            provinsi_ids = provinsi_id
        else:
            provinsi_ids = [str(provinsi_id)]
        
        all_features = []
        for prov_id in provinsi_ids:
            base_params = {
                'wilayah': 'IN',
                'satelit[]': ['NASA-MODIS', 'NASA-SNPP', 'NASA-NOAA20'],
                'confidence[]': ['low', 'medium', 'high'],
                'provinsi': prov_id,
                'kabkota': kabkota_id if kabkota_id else ''
            }
            params = {**base_params, **time_params}
            
            try:
                logging.info(f"Requesting SiPongi API untuk provinsi {prov_id}...")
                response = requests.get(self.sipongi_api_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                features = data.get('features', [])
                logging.info(f"Provinsi {prov_id}: {len(features)} hotspot ditemukan.")
                all_features.extend(features)
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Gagal mengambil data hotspot provinsi {prov_id}: {e}")
        
        logging.info(f"Total hotspot dari {len(provinsi_ids)} provinsi: {len(all_features)}")
        return all_features
    
    def is_hotspot_in_conservation_area(self, hotspot_lat, hotspot_lon):
        hotspot_point = Point(hotspot_lon, hotspot_lat)
        
        for area_id, area_info in self.protected_areas.items():
            area_name = area_info['name']
            geometry = area_info['geometry']
            
            if geometry.contains(hotspot_point) or geometry.touches(hotspot_point):
                logging.info(f"Hotspot at {hotspot_lat:.6f}, {hotspot_lon:.6f} is within {area_name}")
                return True, area_name
        
        return False, None

    def is_hotspot_near_conservation_area(self, hotspot_lat, hotspot_lon, buffer_meters=100):
        hotspot_point = Point(hotspot_lon, hotspot_lat)

        for area_info in self.protected_areas.values():
            geom = area_info['geometry']
            if geom.contains(hotspot_point) or geom.touches(hotspot_point):
                return False, None, None

        # hotspot_gdf = gpd.GeoDataFrame({'geometry': [hotspot_point]}, crs='EPSG:4326')
        # hotspot_point_proj = hotspot_gdf.to_crs('EPSG:32750').geometry.iloc[0]
        hotspot_gdf = gpd.GeoDataFrame({'geometry': [hotspot_point]}, crs='EPSG:3857')
        hotspot_point_proj = hotspot_gdf.to_crs('EPSG:3857').geometry.iloc[0]

        nearest_area = None
        min_distance = float('inf')

        for area_info in self.protected_areas.values():
            area_geom_proj = area_info.get('geometry_proj')
            if area_geom_proj is None:
                continue

            distance_m = hotspot_point_proj.distance(area_geom_proj)

            if distance_m <= buffer_meters and distance_m < min_distance:
                min_distance = distance_m
                nearest_area = area_info['name']

        if nearest_area:
            logging.info(
                f"Hotspot at {hotspot_lat:.6f}, {hotspot_lon:.6f} berada "
                f"{min_distance:.1f}m dari batas {nearest_area}"
            )
            return True, nearest_area, round(min_distance, 1)

        return False, None, None
    
    
    def _process_hotspot(self, feature, processed_hotspots, notifier):

        properties = feature.get('properties', {})
        geometry = feature.get('geometry', {})
        coordinates = geometry.get('coordinates', [])
        
        if len(coordinates) < 2:
            return False

        lon, lat = coordinates[0], coordinates[1]
        
        hotspot_id = f"{lat:.6f}_{lon:.6f}_{properties.get('date_hotspot', '')}"
        
        if hotspot_id in processed_hotspots:
            return False
        
        desa = properties.get('desa', 'Unknown')
        logging.info(f"Mengecek hotspot di {desa} ({lat:.6f}, {lon:.6f})")
        

        is_in_conservation_area, area_name = self.is_hotspot_in_conservation_area(lat, lon)

        if is_in_conservation_area:
            logging.warning(f"HOTSPOT TERDETEKSI di kawasan konservasi: {area_name}")
            logging.warning(f"   Lokasi: {desa}, Koordinat: {lat:.6f}, {lon:.6f}")
            
            notifier.send_hotspot_alert_channel(properties, area_name, lat, lon)
            
            processed_hotspots.add(hotspot_id)
            return True
        else:
            logging.debug(f"Hotspot di {lat:.6f}, {lon:.6f} tidak berada di kawasan konservasi.")
            return False
