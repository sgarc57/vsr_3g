# Scripts Folder Reorganization - Migration Guide

## What Changed

The scripts folder has been reorganized to separate concerns properly:

### Old Structure
```
scripts/
├── lib/                    # Mixed library files
├── *.py                    # Mixed scripts, tests, and tools
├── *.json                  # Data files mixed with code
└── SMS_MANAGEMENT.md       # Documentation mixed with code
```

### New Structure
```
scripts/
├── src/                    # Source code
│   └── modem_sms/         # Main package
│       ├── auth.py
│       ├── sms.py
│       ├── discord_forwarder.py
│       ├── tplink_crypto.py
│       └── sms_puppeteer.py
├── tests/                 # Test and debug scripts
│   ├── debug_sms_api.py
│   ├── test_sms_endpoint.py
│   ├── research_aes.py
│   └── sms_list_puppeteer.py
├── data/                  # Data files
│   ├── sms_forward_har.json
│   ├── sms_menus.json
│   └── test_messages.json
├── docs/                  # Documentation
│   └── SMS_MANAGEMENT.md
├── modem_3g_commands.py   # Main CLI tool
├── sms_console_helper.py  # Browser console helper
└── venv/                  # Virtual environment
```

## Import Changes

### Before
```python
from lib.auth import TPLinkModemAuth
from lib.sms import TPLinkSMS
from lib.discord_forwarder import DiscordForwarder
```

### After
```python
from src.modem_sms.auth import TPLinkModemAuth
from src.modem_sms.sms import TPLinkSMS
from src.modem_sms.discord_forwarder import DiscordForwarder
```

## Updated Files

All import paths have been automatically updated in:
- `modem_3g_commands.py`
- `sms_console_helper.py`
- `tests/debug_sms_api.py`
- `tests/test_sms_endpoint.py`

## Usage (No Changes Required)

All scripts work exactly as before:

```bash
# Main CLI tool
cd scripts
venv/bin/python3 modem_3g_commands.py list

# Console helper
venv/bin/python3 sms_console_helper.py --json-file data/test_messages.json

# Test scripts
venv/bin/python3 tests/debug_sms_api.py
```

## Benefits

1. **Clear Separation**: Source code, tests, data, and docs are now in separate directories
2. **Better Organization**: Easy to find what you need
3. **Maintainability**: Easier to add new features or tests
4. **Professional Structure**: Follows Python best practices
5. **Scalability**: Easy to add more modules or tests

## No Breaking Changes

All existing functionality works exactly as before. The reorganization only affects internal structure, not external behavior.
