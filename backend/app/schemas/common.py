"""Common constants and schemas across API domains."""
import re

BARCODE_REGEX = r"^\d{4,13}$"
BARCODE_PATTERN = re.compile(BARCODE_REGEX)
BARCODE_ERROR_MSG = "barcode must contain 4 to 13 digits"
