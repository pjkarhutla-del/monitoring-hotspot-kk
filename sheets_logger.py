#!/usr/bin/env python3


import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

SHEET_HEADERS = [
    'Hotspot ID',           # A — unique key untuk deduplication
    'Waktu Deteksi',        # B
    'Status',               # C
    'Kawasan Konservasi',   # D
    'Jarak dari Batas (m)', # E
    'Desa',                 # F
    'Kecamatan',            # G
    'Kabupaten/Kota',       # H
    'Latitude',             # I
    'Longitude',            # J
    'Confidence Level',     # K
    'Confidence (%)',       # L
    'Satelit',              # M
    'Waktu Hotspot (API)',  # N
    'Link Google Maps',     # O
]


def _make_hotspot_id(lat, lon, date_hotspot):
    return f"{lat:.6f}_{lon:.6f}_{date_hotspot}"


class SheetsLogger:

    def __init__(self):
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        creds_json     = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')

        if not spreadsheet_id:
            raise ValueError("Environment variable GOOGLE_SPREADSHEET_ID belum diatur.")
        if not creds_json:
            raise ValueError("Environment variable GOOGLE_SERVICE_ACCOUNT_JSON belum diatur.")

        creds_dict = json.loads(creds_json)
        creds      = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client     = gspread.authorize(creds)

        spreadsheet    = client.open_by_key(spreadsheet_id)
        self.worksheet = spreadsheet.sheet1

        self._ensure_headers()


    def _ensure_headers(self):
        first_row = self.worksheet.row_values(1)
        if not first_row:
            self.worksheet.insert_row(SHEET_HEADERS, index=1)
            self.worksheet.format('A1:O1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.18, 'green': 0.18, 'blue': 0.18},
            })
            logging.info("Header berhasil ditambahkan ke Google Sheet.")

    def _get_existing_ids(self):
        all_ids = self.worksheet.col_values(1)
        return set(all_ids[1:])

    def _build_row(self, hotspot_id, detection_time, status, area_name,
                   distance_m, props, lat, lon):
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"
        return [
            hotspot_id,
            detection_time,
            status,
            area_name,
            distance_m,                           
            props.get('desa',             'N/A'),
            props.get('kecamatan',        'N/A'),
            props.get('kabkota',          'N/A'),
            round(lat, 6),
            round(lon, 6),
            props.get('confidence_level', 'N/A'),
            props.get('confidence',       'N/A'),
            props.get('sumber',           'N/A'),
            props.get('date_hotspot',     'N/A'),
            maps_url,
        ]


    def log_batch(self, inside_alerts, near_alerts):

        if not inside_alerts and not near_alerts:
            logging.info("Tidak ada hotspot alert untuk dicatat ke Google Sheet.")
            return 0, 0

        existing_ids = self._get_existing_ids()
        logging.info(f"Google Sheet sudah memiliki {len(existing_ids)} entri sebelumnya.")

        detection_time = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
        new_rows  = []
        skipped   = 0

        for props, area_name, lat, lon in inside_alerts:
            hid = _make_hotspot_id(lat, lon, props.get('date_hotspot', ''))
            if hid in existing_ids:
                logging.debug(f"Duplikat dilewati: {hid}")
                skipped += 1
                continue
            new_rows.append(self._build_row(
                hid, detection_time,
                '⚠️ Di Dalam Kawasan', area_name, '-',
                props, lat, lon,
            ))

        for props, area_name, lat, lon, distance_m in near_alerts:
            hid = _make_hotspot_id(lat, lon, props.get('date_hotspot', ''))
            if hid in existing_ids:
                logging.debug(f"Duplikat dilewati: {hid}")
                skipped += 1
                continue
            new_rows.append(self._build_row(
                hid, detection_time,
                '📏 Buffer 100m', area_name, distance_m,
                props, lat, lon,
            ))

        if new_rows:
            self.worksheet.append_rows(new_rows, value_input_option='USER_ENTERED')
            logging.info(
                f"Google Sheet: {len(new_rows)} baris baru dicatat, "
                f"{skipped} duplikat dilewati."
            )
        else:
            logging.info(f"Google Sheet: semua {skipped} entri sudah ada, tidak ada yang ditulis.")

        return len(new_rows), skipped
