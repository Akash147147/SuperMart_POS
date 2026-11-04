"""HardwareSetting model."""
from datetime import datetime, timezone
from .base import db


class HardwareSetting(db.Model):
    __tablename__ = 'hardware_settings'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    counter_id = db.Column(db.Integer, db.ForeignKey('billing_counters.id'))
    setting_type = db.Column(db.String(50), nullable=False)  # scanner, printer, camera
    config_data = db.Column(db.JSON)
    is_configured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('store_id', 'counter_id', 'setting_type',
                           name='uq_hardware_setting'),
    )

    def __repr__(self):
        return f'<HardwareSetting {self.setting_type}>'

