"""Unit tests for GST calculation service."""
import unittest
from decimal import Decimal
from services.gst_service import calculate_item_tax, calculate_bill_taxes, round_to_nearest


class TestGSTService(unittest.TestCase):

    def test_intra_state_18_percent(self):
        result = calculate_item_tax(
            selling_price=Decimal('100.00'),
            quantity=Decimal('1'),
            gst_percentage=Decimal('18.00'),
            tax_type='intra-state'
        )
        self.assertEqual(result['taxable_amount'], Decimal('100.00'))
        self.assertEqual(result['cgst_amount'], Decimal('9.00'))
        self.assertEqual(result['sgst_amount'], Decimal('9.00'))
        self.assertEqual(result['igst_amount'], Decimal('0.00'))
        self.assertEqual(result['total_tax'], Decimal('18.00'))
        self.assertEqual(result['total_amount'], Decimal('118.00'))

    def test_intra_state_5_percent_with_discount(self):
        # 2 items @ 100 = 200, discount = 20 -> taxable = 180
        # 5% of 180 = 9.00 -> 4.50 CGST, 4.50 SGST
        result = calculate_item_tax(
            selling_price=Decimal('100.00'),
            quantity=Decimal('2'),
            gst_percentage=Decimal('5.00'),
            discount_amount=Decimal('20.00'),
            tax_type='intra-state'
        )
        self.assertEqual(result['taxable_amount'], Decimal('180.00'))
        self.assertEqual(result['cgst_amount'], Decimal('4.50'))
        self.assertEqual(result['sgst_amount'], Decimal('4.50'))
        self.assertEqual(result['total_tax'], Decimal('9.00'))
        self.assertEqual(result['total_amount'], Decimal('189.00'))

    def test_inter_state_igst(self):
        result = calculate_item_tax(
            selling_price=Decimal('200.00'),
            quantity=Decimal('1'),
            gst_percentage=Decimal('12.00'),
            tax_type='inter-state'
        )
        self.assertEqual(result['taxable_amount'], Decimal('200.00'))
        self.assertEqual(result['cgst_amount'], Decimal('0.00'))
        self.assertEqual(result['sgst_amount'], Decimal('0.00'))
        self.assertEqual(result['igst_amount'], Decimal('24.00'))
        self.assertEqual(result['total_tax'], Decimal('24.00'))
        self.assertEqual(result['total_amount'], Decimal('224.00'))

    def test_gst_exempt_item(self):
        result = calculate_item_tax(
            selling_price=Decimal('50.00'),
            quantity=Decimal('3'),
            gst_percentage=Decimal('18.00'),
            is_gst_exempt=True
        )
        self.assertEqual(result['taxable_amount'], Decimal('150.00'))
        self.assertEqual(result['total_tax'], Decimal('0.00'))
        self.assertEqual(result['total_amount'], Decimal('150.00'))

    def test_rounding(self):
        rounded, diff = round_to_nearest(Decimal('159.40'))
        self.assertEqual(rounded, Decimal('159.00'))
        self.assertEqual(diff, Decimal('-0.40'))

        rounded2, diff2 = round_to_nearest(Decimal('159.60'))
        self.assertEqual(rounded2, Decimal('160.00'))
        self.assertEqual(diff2, Decimal('0.40'))


if __name__ == '__main__':
    unittest.main()

