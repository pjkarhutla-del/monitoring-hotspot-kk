#!/usr/bin/env python3

import time
import logging
import os
import sys
import locale
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from hotspot_notification import HotspotMonitor
from broadcast_notification import ChannelNotifier
from sheets_logger import SheetsLogger

def setup_logging():
    try:
        try:
            locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
        except locale.Error:
            logging.warning("Locale 'id_ID.UTF-8' tidak didukung. Menggunakan locale default.")

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/hotspot_monitor.log', mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logging.info("=== LOGGING SETUP COMPLETED ===")
        logging.info(f"Log file: logs/hotspot_monitor.log")
        logging.info(f"Timestamp: {datetime.now(ZoneInfo('Asia/Jakarta'))}")
        
    except Exception as e:
        print(f"Error setting up logging: {e}")
        # Fallback to basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

def process_hotspots(monitor: HotspotMonitor, hotspots: list, buffer_meters: int = 100) -> tuple:
    inside_alerts = []
    near_alerts   = []
    skipped_null_geometry = 0

    for i, feature in enumerate(hotspots):
        properties = feature.get('properties', {})
        geometry = feature.get('geometry')

        if not geometry:
            skipped_null_geometry += 1
            logging.warning(f"Hotspot {i+1} memiliki geometry null/kosong, dilewati.")
            continue

        coordinates = geometry.get('coordinates', [])
        
        if len(coordinates) >= 2:
            lon, lat = coordinates[0], coordinates[1]
            desa = properties.get('desa', 'Tidak Diketahui')

            logging.info("-" * 60)
            logging.info(f"HOTSPOT #{i+1}")
            logging.info(f"Desa      : {desa}")
            logging.info(f"Latitude  : {lat}")
            logging.info(f"Longitude : {lon}")

            is_inside, area_name = monitor.is_hotspot_in_conservation_area(lat, lon)

            logging.info(
            f"Hasil cek kawasan konservasi -> "
            f"inside={is_inside}, area={area_name}"
)
            if is_inside:
                logging.warning(f"HOTSPOT DI DALAM kawasan konservasi: {area_name}")
                logging.warning(f"   Lokasi: {desa}, Koordinat: {lat:.6f}, {lon:.6f}")
                inside_alerts.append((properties, area_name, lat, lon))
                continue 

            is_near, near_area_name, distance_m = monitor.is_hotspot_near_conservation_area(
                lat, lon, buffer_meters
            )
            logging.info(
                f"Hasil cek buffer -> "
                f"near={is_near}, "
                f"area={near_area_name}, "
                f"jarak={distance_m}"
            )
            if is_near:
                logging.warning(
                    f"HOTSPOT DEKAT batas kawasan: {near_area_name} (jarak: {distance_m}m)"
                )
                logging.warning(f"   Lokasi: {desa}, Koordinat: {lat:.6f}, {lon:.6f}")
                near_alerts.append((properties, near_area_name, lat, lon, distance_m))
            else:
                logging.debug(f"Hotspot {i+1} tidak berada di/dekat kawasan konservasi")

    if skipped_null_geometry > 0:
        logging.warning(f"Total {skipped_null_geometry} hotspot dilewati karena geometry null.")

    return inside_alerts, near_alerts

def run_daily_check():
    setup_logging()
    logging.info("=== STARTING DAILY HOTSPOT CHECK ===")
    logging.info(f"Check started at: {datetime.now(ZoneInfo('Asia/Jakarta'))}")
    
    try:
        monitor = HotspotMonitor()
        notifier = ChannelNotifier()
        logging.info("HotspotMonitor dan ChannelNotifier berhasil diinisialisasi.")
        
        logging.info("Mengambil data hotspot dari API SiPongi...")
        hotspots = monitor.get_hotspot_data()
        total_fetched = len(hotspots)
        logging.info(f"Diterima {total_fetched} data hotspot.")

        logging.info("=" * 70)
        logging.info("HASIL PENGAMBILAN DATA HOTSPOT")
        logging.info(f"Total hotspot dari API SiPongi : {total_fetched}")

        if total_fetched > 0:
            sample = hotspots[0]
            logging.info(f"Sample hotspot pertama: {sample}")

        logging.info("=" * 70)


        if total_fetched == 0:
            logging.warning(
                "API SiPongi mengembalikan 0 data hotspot. "
                "Kemungkinan ada gangguan pada API atau koneksi. "
                "Mengirim peringatan ke Telegram."
            )
            notifier.send_api_fetch_warning()
            return
        
        inside_alerts, near_alerts = process_hotspots(monitor, hotspots)
        
        logging.info("=" * 70)
        logging.info("HASIL ANALISIS HOTSPOT")
        logging.info(f"Total hotspot              : {len(hotspots)}")
        logging.info(f"Hotspot di dalam kawasan   : {len(inside_alerts)}")
        logging.info(f"Hotspot dekat batas        : {len(near_alerts)}")
        logging.info("=" * 70)

        hotspots_in_protected_areas = len(inside_alerts)
        hotspots_near_boundary      = len(near_alerts)

        if inside_alerts:
            notifier.send_consolidated_hotspot_alert(inside_alerts)

        if near_alerts:
            notifier.send_near_boundary_alert(near_alerts)

        if inside_alerts or near_alerts:
            try:
                sheets = SheetsLogger()
                ditulis, dilewati = sheets.log_batch(inside_alerts, near_alerts)
                logging.info(f"Google Sheet: {ditulis} baris baru, {dilewati} duplikat dilewati.")
            except Exception as e:
                logging.error(f"Gagal mencatat ke Google Sheet (monitoring tetap berjalan): {e}")

        logging.info(
            f"Daily Summary: {hotspots_in_protected_areas} hotspot di dalam kawasan, "
            f"{hotspots_near_boundary} hotspot dalam buffer 100m dari batas kawasan."
        )

        try:
            current_date = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%A, %d %B %Y")
            notifier.send_daily_summary_channel(
                hotspots_in_protected_areas, current_date, total_fetched, hotspots_near_boundary
            )
            logging.info("Ringkasan harian berhasil dikirim ke channel.")
        except Exception as e:
            logging.error(f"Gagal mengirim ringkasan harian: {e}")
            
    except Exception as e:
        logging.error(f"Error in daily hotspot check: {e}")
        logging.error(f"Error details: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")

def main():
    print("=== Memulai Eksekusi Monitor Hotspot Harian ===")
    
    run_daily_check()
    
    print("\n=== Pengecekan Selesai ===")
    print(f"Log detail tersimpan di: logs/hotspot_monitor.log")

if __name__ == "__main__":
    main() 