"""Common constants and schemas across API domains."""
import re

BARCODE_REGEX = r"^\d{6,15}$"
BARCODE_PATTERN = re.compile(BARCODE_REGEX)
BARCODE_ERROR_MSG = "barcode must contain 6 to 15 digits"
