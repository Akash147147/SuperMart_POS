"""Printing service - handles print configuration and preparation."""


def get_receipt_css(paper_width='80mm', font_size='12px', margins='5mm'):
    """Generate CSS for thermal receipt printing."""
    
    width_map = {
        '58mm': '48mm',  # printable area
        '80mm': '72mm',  # printable area
    }
    printable = width_map.get(paper_width, '72mm')
    
    return f"""
    @media print {{
        @page {{
            size: {paper_width} auto;
            margin: {margins};
        }}
        
        body * {{
            visibility: hidden;
        }}
        
        .receipt-container, .receipt-container * {{
            visibility: visible;
        }}
        
        .receipt-container {{
            position: absolute;
            left: 0;
            top: 0;
            width: {printable};
            font-size: {font_size};
            font-family: 'Courier New', monospace;
            color: #000;
        }}
        
        .no-print {{
            display: none !important;
        }}
        
        .receipt-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .receipt-table th, .receipt-table td {{
            padding: 1px 2px;
            font-size: {font_size};
        }}
        
        .receipt-header {{
            text-align: center;
            margin-bottom: 5px;
        }}
        
        .receipt-footer {{
            text-align: center;
            margin-top: 5px;
        }}
        
        .receipt-divider {{
            border-top: 1px dashed #000;
            margin: 3px 0;
        }}
    }}
    """


def get_a4_receipt_css():
    """Generate CSS for A4 invoice printing."""
    return """
    @media print {
        @page {
            size: A4;
            margin: 15mm;
        }
        
        body * {
            visibility: hidden;
        }
        
        .receipt-container, .receipt-container * {
            visibility: visible;
        }
        
        .receipt-container {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            font-family: Arial, sans-serif;
            color: #000;
        }
        
        .no-print {
            display: none !important;
        }
    }
    """

