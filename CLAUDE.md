# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QWatch Pro is a reverse-engineered BLE (Bluetooth Low Energy) client for the QWatch Pro smartwatch (QWatch_Pro_1.0.2.83.apk, package `com.qcwireless.qcwatch`). The project extracts the BLE communication protocol from the decompiled Android APK and reimplements it as a Python CLI tool for Linux.

## Architecture

- `qwatch_hr.py` — Main Python script. BLE client that connects to a QWatch Pro smartwatch and streams real-time heart rate data. Uses the `bleak` library for cross-platform BLE communication.
- `jadx_output/` — Decompiled Java source from the APK (via JADX). Reference material for reverse-engineering the BLE protocol. Key classes are under `com.oudmon.ble.base.communication`.
- `apk_extract/` — Raw APK contents (native libs, metadata, resources).

## BLE Protocol

All communication uses 16-byte packets:
- **Service UUID:** `6e40fff0-b5a3-f393-e0a9-e50e24dcca9e`
- **Write Characteristic:** `6e400002-b5a3-f393-e0a9-e50e24dcca9e`
- **Notify Characteristic:** `6e400003-b5a3-f393-e0a9-e50e24dcca9e`
- **Packet format:** byte 0 = command key, bytes 1-14 = payload, byte 15 = CRC (sum of bytes 0-14 & 0xFF)

Key commands: 105 (start measurement), 106 (stop), 30 (realtime HR), 21 (stored HR), 3 (battery).

## Running

```bash
# Install dependency
pip install bleak

# Scan for nearby watches
python3 qwatch_hr.py

# Connect to a specific device by MAC address
python3 qwatch_hr.py AA:BB:CC:DD:EE:FF
```

Requires Linux with Bluetooth support. The script scans for devices matching QWatch-like names or the known service UUID.
