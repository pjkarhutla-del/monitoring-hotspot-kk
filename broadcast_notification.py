#!/usr/bin/env python3

import requests
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

load_dotenv()

class ChannelNotifier:
    def __init__(self):

        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        self.base_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"
        
    def send_channel_message(self, message):

        if not self.telegram_bot_token or not self.telegram_channel_id:
            logging.warning("Telegram credentials not configured")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.telegram_channel_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logging.info(f"Pesan berhasil dikirim ke channel: {self.telegram_channel_id}")
            return True
            
        except Exception as e:
            logging.error(f"Gagal mengirim pesan ke channel: {e}")
            return False
    
    def send_hotspot_alert_channel(self, hotspot_data, protected_area_name, lat=None, lon=None):

        detection_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        
        coordinates_text = ""
        if lat is not None and lon is not None:
            coordinates_text = f"""• Latitude: {lat:.6f}
            • Longitude: {lon:.6f}"""
        
        message = f"""
🚨 <b>HOTSPOT ALERT</b> 🚨

📍 <b>Titik Hotspot masuk Kawasan Konservasi:</b> {protected_area_name}
🌡️ <b>Hotspot Details:</b>
   • Desa: {hotspot_data.get('desa', 'N/A')}
   • Kecamatan: {hotspot_data.get('kecamatan', 'N/A')}
   • Kabupaten: {hotspot_data.get('kabkota', 'N/A')}
   {coordinates_text}
   • Confidence: {hotspot_data.get('confidence_level', 'N/A')} ({hotspot_data.get('confidence', 'N/A')})
   • Satellite: {hotspot_data.get('sumber', 'N/A')}
   • Date/Time: {hotspot_data.get('date_hotspot', 'N/A')}

⏰ <b>Waktu Deteksi:</b> {detection_time}

⚠️ <b>Tindakan yang Diperlukan:</b>
   • Verifikasi lokasi titik api (hotspot)
   • Koordinasi dengan pihak berwenang setempat
   • Siapkan tim pemadam kebakaran
   • Pantau situasi dengan cermat

#HotspotAlert #KawasanKonservasi #FirePrevention
        """
        
        return self.send_channel_message(message.strip())
    
    def send_consolidated_hotspot_alert(self, hotspot_details):

        if not hotspot_details:
            return True

        detection_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        
        message_parts = [f"🚨 <b>HOTSPOT ALERT ({len(hotspot_details)} LOKASI)</b> 🚨\n"]

        for i, (hotspot_data, protected_area_name, lat, lon) in enumerate(hotspot_details, 1):
            coordinates_text = f"""• Latitude: {lat:.6f}
   • Longitude {lon:.6f}""" if lat is not None and lon is not None else ""
            
            part = f"""
<b>{i}. Lokasi: {hotspot_data.get('desa', 'N/A')}, {hotspot_data.get('kecamatan', 'N/A')}, {hotspot_data.get('kabkota', 'N/A')}</b>
🌡️ <b>Hotspot Details:</b>
   •📍 Kawasan Konservasi: {protected_area_name}
   {coordinates_text}
   • Confidence: {hotspot_data.get('confidence_level', 'N/A')}({hotspot_data.get('confidence', 'N/A')}%)
   • Satelit: {hotspot_data.get('sumber', 'N/A')}
   • Waktu Hotspot: {hotspot_data.get('date_hotspot', 'N/A')}
   • Google Maps: https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}
   """
            message_parts.append(part)

        message_parts.append(f"\n⏰ <b>Waktu Deteksi Laporan:</b> {detection_time}")
        message_parts.append(f"""\n⚠️ <b>Tindakan yang Diperlukan:</b>
        • Verifikasi lokasi titik api (hotspot)
        • Koordinasi dengan pihak berwenang setempat
        • Siapkan tim pemadam kebakaran
        • Pantau situasi dengan cermat\n""")
        message_parts.append("#HotspotAlert #KawasanKonservasi #FirePrevention")
        
        full_message = "".join(message_parts)
        return self.send_channel_message(full_message.strip())

    def send_api_fetch_warning(self):

        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
⚠️ <b>PERINGATAN SISTEM MONITORING</b> ⚠️

📡 <b>Status:</b> API SiPongi mengembalikan 0 data hotspot
🕐 <b>Waktu:</b> {timestamp}

❓ <b>Kemungkinan Penyebab:</b>
   • SiPongi sedang dalam maintenance / refresh data
   • Gangguan koneksi ke server SiPongi
   • Perubahan format atau struktur response API

⚡ <b>Tindakan yang Diperlukan:</b>
   • Cek manual hotspot di <a href="https://sipongidata.my.id">sipongidata.my.id</a>
   • Data periode ini mungkin tidak akurat
   • Monitoring akan dilanjutkan pada jadwal berikutnya

<i>Notifikasi ini dikirim otomatis karena tidak ada data yang diterima dari API.</i>

#SystemAlert #APIWarning #HotspotMonitoring
        """

        logging.warning("Mengirim peringatan API ke channel Telegram.")
        return self.send_channel_message(message.strip())


    def send_near_boundary_alert(self, near_alert_details):

        if not near_alert_details:
            return True

        detection_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        count = len(near_alert_details)

        message_parts = [
            f"📍 <b>HOTSPOT MENDEKATI KAWASAN KONSERVASI ({count} LOKASI)</b> 📍\n\n"
            f"<i>Titik-titik berikut berada dalam radius 100\u202fm dari batas kawasan konservasi.</i>\n"
        ]

        for i, (hotspot_data, area_name, lat, lon, distance_m) in enumerate(near_alert_details, 1):
            desa      = hotspot_data.get('desa', 'N/A')
            kecamatan = hotspot_data.get('kecamatan', 'N/A')
            kabkota   = hotspot_data.get('kabkota', 'N/A')
            conf_lvl  = hotspot_data.get('confidence_level', 'N/A')
            conf_pct  = hotspot_data.get('confidence', 'N/A')
            satelit   = hotspot_data.get('sumber', 'N/A')
            waktu     = hotspot_data.get('date_hotspot', 'N/A')
            maps_url  = f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"

            part = f"""
<b>{i}. {desa}, {kecamatan}, {kabkota}</b>
   • 🏞️ Kawasan Terdekat : {area_name}
   • 📏 Jarak dari Batas  : <b>{distance_m} meter</b>
   • 📍 Koordinat         : {lat:.6f}, {lon:.6f}
   • 🔥 Confidence        : {conf_lvl} ({conf_pct}%)
   • 🛰️ Satelit           : {satelit}
   • 📅 Waktu Hotspot     : {waktu}
   • 🗺️ <a href="{maps_url}">Lihat di Google Maps</a>
"""
            message_parts.append(part)

        message_parts.append(
            f"\n⏰ <b>Waktu Deteksi:</b> {detection_time}\n"
            f"⚠️ <b>Tindakan yang Disarankan:</b>\n"
            f"   • Pantau pergerakan titik api secara ketat\n"
            f"   • Koordinasi dengan petugas lapangan terdekat\n"
            f"   • Antisipasi potensi api masuk kawasan konservasi\n\n"
            f"#HotspotBuffer #KawasanKonservasi #Waspada"
        )

        full_message = "".join(message_parts)
        return self.send_channel_message(full_message.strip())

    def send_daily_summary_channel(self, hotspot_count, date_str=None, total_fetched=None, near_boundary_count=0):

        if date_str is None:
            date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%A, %d %B %Y")

        if hotspot_count == 0 and near_boundary_count == 0:
            status_icon   = "✅"
            status_text   = "Tidak ada hotspot di dalam maupun dekat kawasan konservasi"
            result_status = "Aman"
        elif hotspot_count == 0 and near_boundary_count > 0:
            status_icon   = "🟡"
            status_text   = "Tidak ada hotspot di dalam kawasan, namun ada yang mendekati batas"
            result_status = "Siaga"
        else:
            status_icon   = "⚠️"
            status_text   = f"{hotspot_count} hotspot terdeteksi di dalam kawasan konservasi"
            result_status = "Waspada"

        fetch_info = ""
        if total_fetched is not None:
            fetch_info = f"\n   • Total hasil scanning hotspot dari SiPongi : {total_fetched} titik"

        near_info = ""
        if near_boundary_count > 0:
            near_info = f"\n   • Hotspot dalam buffer 100m batas : {near_boundary_count} titik ⚠️"

        message = f"""
📊 <b>DAILY SUMMARY</b> 📊

📅 <b>Tanggal:</b> {date_str}
{status_icon} <b>Status:</b> {status_text}

🎯 <b>Monitoring Result:</b>
   • Hotspot di dalam kawasan konservasi: {hotspot_count}{near_info}{fetch_info}
   • Status Keseluruhan: {result_status}

#DailySummary #HotspotMonitoring
        """

        return self.send_channel_message(message.strip())
