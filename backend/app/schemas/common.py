"""Common constants and schemas across API domains."""
import re

BARCODE_REGEX = r"^\d{4,13}$"
BARCODE_PATTERN = re.compile(BARCODE_REGEX)
BARCODE_ERROR_MSG = "barcode must contain 4 to 13 digits"

ANDROID_APP_ID_REGEX = r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$"
ANDROID_APP_ID_PATTERN = re.compile(ANDROID_APP_ID_REGEX)
ANDROID_APP_ID_ERROR_MSG = "Invalid Android package format for app_id"
