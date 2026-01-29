# Scripts Directory Structure

This directory contains the SMS management system for the TP-Link 3G modem.

## Directory Structure

```
scripts/
├── src/                    # Source code
│   └── modem_sms/         # Main package
│       ├── __init__.py
│       ├── auth.py        # Authentication module
│       ├── sms.py         # SMS operations
│       ├── discord_forwarder.py
│       └── tplink_crypto.py
├── tests/                 # Test and debug scripts
│   ├── debug_sms_api.py
│   ├── test_sms_endpoint.py
│   └── research_aes.py
├── data/                  # Data files (HAR captures, JSON)
│   ├── sms_forward_har.json
│   └── sms_menus.json
├── docs/                  # Documentation
│   └── SMS_MANAGEMENT.md
├── modem_3g_commands.py   # Main CLI tool
├── sms_console_helper.py  # Browser console helper
└── venv/                  # Virtual environment

## Main Scripts

- **modem_3g_commands.py** - Main CLI tool for SMS operations
- **sms_console_helper.py** - Helper for browser console-based SMS retrieval

## Usage

See `docs/SMS_MANAGEMENT.md` for detailed usage instructions.
