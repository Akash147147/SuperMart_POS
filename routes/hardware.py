"""Hardware settings routes - scanner, printer, and camera configuration."""
from datetime import datetime

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from models.base import db
from models.store import Store
from models.hardware import HardwareSetting
from models.audit import AuditLog

hardware_bp = Blueprint('hardware', __name__)


def _log_audit(action, entity_type=None, entity_id=None, details=None):
    """Create an audit log entry."""
    log = AuditLog(
        store_id=current_user.store_id,
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(log)


def _get_or_create_setting(store_id, counter_id, setting_type):
    """Retrieve an existing hardware setting or create a new one."""
    setting = HardwareSetting.query.filter_by(
        store_id=store_id,
        counter_id=counter_id,
        setting_type=setting_type,
    ).first()

    if not setting:
        setting = HardwareSetting(
            store_id=store_id,
            counter_id=counter_id,
            setting_type=setting_type,
            config_data={},
            is_configured=False,
        )
        db.session.add(setting)

    return setting


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------

@hardware_bp.route('/hardware')
@login_required
def hardware_page():
    """Render the hardware settings page."""
    return render_template('hardware.html')


# ---------------------------------------------------------------------------
# Get all hardware settings for the current counter
# ---------------------------------------------------------------------------

@hardware_bp.route('/api/hardware/settings', methods=['GET'])
@login_required
def get_hardware_settings():
    """Return all hardware settings for the current counter."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        counter_id = request.args.get('counter_id', type=int)

        settings = HardwareSetting.query.filter_by(
            store_id=store.id,
            counter_id=counter_id,
        ).all()

        data = {}
        for s in settings:
            data[s.setting_type] = {
                'id': s.id,
                'config_data': s.config_data or {},
                'is_configured': s.is_configured,
                'updated_at': s.updated_at.isoformat() if s.updated_at else None,
            }

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Save scanner configuration
# ---------------------------------------------------------------------------

@hardware_bp.route('/api/hardware/settings/scanner', methods=['POST'])
@login_required
def save_scanner_config():
    """Save barcode scanner configuration."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        counter_id = data.get('counter_id')
        setting = _get_or_create_setting(store.id, counter_id, 'scanner')

        config = {
            'scanner_type': data.get('scanner_type', 'usb'),  # usb, bluetooth, camera
            'suffix_char': data.get('suffix_char', 'Enter'),
            'prefix_char': data.get('prefix_char', ''),
            'scan_delay_ms': data.get('scan_delay_ms', 50),
            'auto_submit': data.get('auto_submit', True),
            'beep_on_scan': data.get('beep_on_scan', True),
        }

        setting.config_data = config
        setting.is_configured = True

        _log_audit('update_scanner_config', 'hardware_setting', setting.id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Scanner configuration saved successfully',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Save printer configuration
# ---------------------------------------------------------------------------

@hardware_bp.route('/api/hardware/settings/printer', methods=['POST'])
@login_required
def save_printer_config():
    """Save receipt printer configuration."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        counter_id = data.get('counter_id')
        setting = _get_or_create_setting(store.id, counter_id, 'printer')

        config = {
            'paper_width': data.get('paper_width', '80mm'),
            'font_size': data.get('font_size', 12),
            'margin_left': data.get('margin_left', 5),
            'margin_right': data.get('margin_right', 5),
            'margin_top': data.get('margin_top', 5),
            'margin_bottom': data.get('margin_bottom', 5),
            'printer_name': data.get('printer_name', ''),
            'use_qz_tray': data.get('use_qz_tray', False),
            'auto_print': data.get('auto_print', False),
            'print_copies': data.get('print_copies', 1),
        }

        setting.config_data = config
        setting.is_configured = True

        _log_audit('update_printer_config', 'hardware_setting', setting.id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Printer configuration saved successfully',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Save camera configuration
# ---------------------------------------------------------------------------

@hardware_bp.route('/api/hardware/settings/camera', methods=['POST'])
@login_required
def save_camera_config():
    """Save camera / barcode scanner camera configuration."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        counter_id = data.get('counter_id')
        setting = _get_or_create_setting(store.id, counter_id, 'camera')

        config = {
            'preferred_camera_id': data.get('preferred_camera_id', ''),
            'scan_delay': data.get('scan_delay', 500),
            'resolution_width': data.get('resolution_width', 640),
            'resolution_height': data.get('resolution_height', 480),
            'mirror': data.get('mirror', False),
            'torch': data.get('torch', False),
        }

        setting.config_data = config
        setting.is_configured = True

        _log_audit('update_camera_config', 'hardware_setting', setting.id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Camera configuration saved successfully',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Test print
# ---------------------------------------------------------------------------

@hardware_bp.route('/api/hardware/test-print', methods=['POST'])
@login_required
def test_print():
    """Generate a test receipt HTML for printer testing."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        paper_width = request.json.get('paper_width', '80mm') if request.is_json else '80mm'

        test_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{
    font-family: 'Courier New', monospace;
    width: {paper_width};
    margin: 0 auto;
    padding: 5mm;
    font-size: 12px;
  }}
  .center {{ text-align: center; }}
  .separator {{ border-top: 1px dashed #000; margin: 5px 0; }}
  .bold {{ font-weight: bold; }}
  .row {{ display: flex; justify-content: space-between; }}
</style>
</head>
<body>
  <div class="center bold">{store.name or 'SuperMart POS'}</div>
  <div class="center">{store.address or 'Store Address'}</div>
  <div class="center">{store.city or 'City'}, {store.state or 'State'} - {store.pincode or '000000'}</div>
  <div class="center">Ph: {store.phone or '0000000000'}</div>
  <div class="center">GSTIN: {store.gstin or 'N/A'}</div>
  <div class="separator"></div>
  <div class="center bold">*** TEST PRINT ***</div>
  <div class="separator"></div>
  <div class="row"><span>Item 1</span><span>₹100.00</span></div>
  <div class="row"><span>Item 2</span><span>₹200.00</span></div>
  <div class="row"><span>Item 3</span><span>₹150.00</span></div>
  <div class="separator"></div>
  <div class="row bold"><span>TOTAL</span><span>₹450.00</span></div>
  <div class="separator"></div>
  <div class="center">Printed at: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</div>
  <div class="center">Paper Width: {paper_width}</div>
  <div class="separator"></div>
  <div class="center">{store.receipt_footer or 'Thank You! Visit Again!'}</div>
</body>
</html>"""

        return jsonify({
            'success': True,
            'message': 'Test receipt generated',
            'data': {'receipt_html': test_html},
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
