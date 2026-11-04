"""Barcode service - validation and lookup."""
import re


# Supported barcode formats
BARCODE_PATTERNS = {
    'EAN-13': re.compile(r'^\d{13}$'),
    'EAN-8': re.compile(r'^\d{8}$'),
    'UPC-A': re.compile(r'^\d{12}$'),
    'UPC-E': re.compile(r'^\d{6,8}$'),
    'CODE128': re.compile(r'^[\x00-\x7F]{1,80}$'),
}


def identify_barcode_format(barcode):
    """Identify the format of a barcode string."""
    barcode = barcode.strip()
    for fmt, pattern in BARCODE_PATTERNS.items():
        if pattern.match(barcode):
            return fmt
    return 'UNKNOWN'


def validate_ean13_checksum(barcode):
    """Validate EAN-13 check digit."""
    if len(barcode) != 13 or not barcode.isdigit():
        return False
    
    total = 0
    for i, digit in enumerate(barcode[:12]):
        if i % 2 == 0:
            total += int(digit)
        else:
            total += int(digit) * 3
    
    check = (10 - (total % 10)) % 10
    return check == int(barcode[12])


def clean_barcode(barcode):
    """Clean barcode input - strip whitespace and common scanner suffixes."""
    if not barcode:
        return ''
    # Strip whitespace and common suffix characters
    cleaned = barcode.strip().rstrip('\r\n\t')
    return cleaned

