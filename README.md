# SuperMart POS — Production Operations & Engineering Manual

**Universal Supermarket Billing, Inventory, Hardware Integration and Retail Management Platform**

---

## 1. System Architecture

SuperMart POS is designed as a standalone, offline-ready retail POS solution running locally on Windows:
- **Backend:** Python / Flask application factory with REST API endpoints and Flask-Login session management.
- **Data Layer:** SQLAlchemy ORM with dual-engine support:
  - **Production:** MySQL 8 with connection pooling and utf8mb4 charset.
  - **Local/Offline:** Embedded SQLite (`supermart.db`) automatically activated when MySQL is not present.
- **Financial & Tax Engine:** Strict Python `Decimal` arithmetic for all currency, discount, and GST calculations. Floating-point arithmetic is never used for money.
- **Frontend:** Responsive, minimal UI built on Bootstrap 5 and custom POS styles (`/static/css/style.css`).
- **Hardware Layer:**
  - Barcode Scanners: USB/Bluetooth keyboard emulation (HID) and webcam scanning via the ZXing browser engine.
  - Printers: Thermal receipt printer formatting (58mm, 80mm) with native browser print fallback and print CSS.

---

## 2. Installation & Quick Start

### Quick Launch on Windows:
Double-click `start_pos.bat` or run:
```powershell
cd "d:\Barcode scanner\Scanner_2\SuperMart_POS"
python app.py
```

### Accessing the Web Interface:
- **URL:** [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Administrator / Owner:**
  - Username: `admin`
  - Password: `admin123`
- **Cashier:**
  - Username: `cashier`
  - Password: `cashier123`

---

## 3. Core Modules & Endpoints

| Module | Route / Page | Capabilities |
| :--- | :--- | :--- |
| **Login & Auth** | `/login` | Role-based authentication (`admin`, `cashier`), password hashing, secure sessions. |
| **Dashboard** | `/` or `/dashboard` | Today's revenue, completed bills, total items sold, low-stock alerts, monthly trends. |
| **Billing Counter** | `/billing` | Continuous scanning, auto-quantity increment, line discounts, GST breakdown, cash change calculator, thermal receipt generation. |
| **Product Catalog** | `/products` | CRUD operations, barcode assignment, HSN code, pricing (MRP vs. Selling), GST rate brackets, bulk CSV import/export. |
| **Inventory** | `/inventory` | Live stock levels, Stock-In batch additions, stock adjustments, wastage/damage tracking, movement logs. |
| **Sales History** | `/sales` | Paginated invoice archives, filter by date/payment mode, reprint receipts, PDF downloads. |
| **Reports** | `/reports` | Revenue metrics, GST tax summary by rate bracket, product-wise and category-wise performance. |
| **Hardware** | `/hardware` | Live barcode scanner test terminal and thermal printer test receipt generator. |
| **Store Settings** | `/settings` | Supermarket name, GSTIN, phone, address, paper width (58mm vs 80mm), receipt footer note. |

---

## 4. Hardware Configuration Guide

### 1. Barcode Scanners (USB / Wireless Bluetooth):
1. Plug in your USB scanner or pair via Bluetooth.
2. Ensure the scanner is in **HID (Keyboard Emulation)** mode with an **Enter suffix** (factory default on 99% of retail scanners).
3. Open `/hardware` in SuperMart POS to test. Scan any barcode—the test input should immediately display the value.
4. On the `/billing` counter screen, the cursor auto-focuses on the scan box. Rapid successive scans automatically accumulate quantities on matching items.

### 2. Thermal Receipt Printers (58mm & 80mm):
1. Install your printer driver in Windows (ESC/POS compatible).
2. Go to **Settings** (`/settings`) and select your default paper width (`80mm` or `58mm`).
3. Set the thermal printer as your default Windows printer or select it during the initial print dialog.
4. SuperMart POS utilizes dedicated `@media print` stylesheets that strip browser headers, footers, and margins, delivering aligned supermarket receipts.

---

## 5. Automated Verification & Testing

To run the complete automated test suite (GST tax calculations, atomic inventory deduction, and barcode lookup):
```powershell
cd "d:\Barcode scanner\Scanner_2\SuperMart_POS"
$env:PYTHONPATH="."
python -m unittest discover -s tests -p "test_*.py"
```

