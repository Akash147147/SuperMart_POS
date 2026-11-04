"""GST calculation service using Decimal arithmetic."""
from decimal import Decimal, ROUND_HALF_UP

# Standard GST rates
GST_RATES = [
    Decimal('0.00'),
    Decimal('5.00'),
    Decimal('12.00'),
    Decimal('18.00'),
    Decimal('28.00'),
]

TWO_PLACES = Decimal('0.01')


def calculate_item_tax(selling_price, quantity, gst_percentage, cess_percentage=Decimal('0.00'),
                       discount_amount=Decimal('0.00'), tax_type='intra-state',
                       is_gst_exempt=False):
    """
    Calculate GST for a single item.
    
    All inputs should be Decimal.
    Returns dict with all tax components.
    """
    selling_price = Decimal(str(selling_price))
    quantity = Decimal(str(quantity))
    gst_percentage = Decimal(str(gst_percentage))
    cess_percentage = Decimal(str(cess_percentage))
    discount_amount = Decimal(str(discount_amount))

    # Line total before discount
    line_total = (selling_price * quantity).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    
    # Apply discount
    taxable_amount = (line_total - discount_amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if taxable_amount < Decimal('0.00'):
        taxable_amount = Decimal('0.00')

    cgst_amount = Decimal('0.00')
    sgst_amount = Decimal('0.00')
    igst_amount = Decimal('0.00')
    cess_amount = Decimal('0.00')

    if not is_gst_exempt and gst_percentage > Decimal('0.00'):
        if tax_type == 'intra-state':
            half_rate = (gst_percentage / Decimal('2')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            cgst_amount = (taxable_amount * half_rate / Decimal('100')).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP)
            sgst_amount = (taxable_amount * half_rate / Decimal('100')).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            igst_amount = (taxable_amount * gst_percentage / Decimal('100')).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP)

    if cess_percentage > Decimal('0.00'):
        cess_amount = (taxable_amount * cess_percentage / Decimal('100')).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP)

    total_tax = (cgst_amount + sgst_amount + igst_amount + cess_amount).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP)
    total_amount = (taxable_amount + total_tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return {
        'line_total': line_total,
        'taxable_amount': taxable_amount,
        'gst_percentage': gst_percentage,
        'cgst_rate': (gst_percentage / Decimal('2')).quantize(TWO_PLACES) if tax_type == 'intra-state' else Decimal('0.00'),
        'cgst_amount': cgst_amount,
        'sgst_rate': (gst_percentage / Decimal('2')).quantize(TWO_PLACES) if tax_type == 'intra-state' else Decimal('0.00'),
        'sgst_amount': sgst_amount,
        'igst_rate': gst_percentage if tax_type == 'inter-state' else Decimal('0.00'),
        'igst_amount': igst_amount,
        'cess_percentage': cess_percentage,
        'cess_amount': cess_amount,
        'total_tax': total_tax,
        'total_amount': total_amount,
    }


def calculate_bill_taxes(items_data, tax_type='intra-state'):
    """
    Calculate tax totals for an entire bill.
    
    items_data: list of dicts with item tax details from calculate_item_tax
    Returns summary grouped by GST rate and grand totals.
    """
    # Group by GST percentage
    tax_groups = {}
    for item in items_data:
        rate = item['gst_percentage']
        if rate not in tax_groups:
            tax_groups[rate] = {
                'gst_percentage': rate,
                'taxable_amount': Decimal('0.00'),
                'cgst_rate': item.get('cgst_rate', Decimal('0.00')),
                'cgst_amount': Decimal('0.00'),
                'sgst_rate': item.get('sgst_rate', Decimal('0.00')),
                'sgst_amount': Decimal('0.00'),
                'igst_rate': item.get('igst_rate', Decimal('0.00')),
                'igst_amount': Decimal('0.00'),
                'cess_rate': item.get('cess_percentage', Decimal('0.00')),
                'cess_amount': Decimal('0.00'),
                'total_tax': Decimal('0.00'),
            }
        g = tax_groups[rate]
        g['taxable_amount'] += item['taxable_amount']
        g['cgst_amount'] += item['cgst_amount']
        g['sgst_amount'] += item['sgst_amount']
        g['igst_amount'] += item['igst_amount']
        g['cess_amount'] += item['cess_amount']
        g['total_tax'] += item['total_tax']

    # Quantize group totals
    for g in tax_groups.values():
        for key in ['taxable_amount', 'cgst_amount', 'sgst_amount', 'igst_amount',
                     'cess_amount', 'total_tax']:
            g[key] = g[key].quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Grand totals
    total_taxable = sum(g['taxable_amount'] for g in tax_groups.values())
    total_cgst = sum(g['cgst_amount'] for g in tax_groups.values())
    total_sgst = sum(g['sgst_amount'] for g in tax_groups.values())
    total_igst = sum(g['igst_amount'] for g in tax_groups.values())
    total_cess = sum(g['cess_amount'] for g in tax_groups.values())
    total_tax = sum(g['total_tax'] for g in tax_groups.values())

    return {
        'tax_groups': list(tax_groups.values()),
        'total_taxable': total_taxable.quantize(TWO_PLACES),
        'total_cgst': total_cgst.quantize(TWO_PLACES),
        'total_sgst': total_sgst.quantize(TWO_PLACES),
        'total_igst': total_igst.quantize(TWO_PLACES),
        'total_cess': total_cess.quantize(TWO_PLACES),
        'total_tax': total_tax.quantize(TWO_PLACES),
    }


def round_to_nearest(amount, precision='1'):
    """Round amount to nearest integer (for final bill rounding)."""
    amount = Decimal(str(amount))
    precision = Decimal(str(precision))
    rounded = amount.quantize(precision, rounding=ROUND_HALF_UP)
    round_off = (rounded - amount).quantize(TWO_PLACES)
    return rounded, round_off

