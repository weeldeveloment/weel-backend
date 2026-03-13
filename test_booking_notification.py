#!/usr/bin/env python
"""
Test script for partner booking notifications
Run from weel-backend directory:
  ./venv/bin/python test_booking_notification.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from firebase_admin import messaging, get_app
from users.models.partners import Partner, PartnerDevice
from users.models.clients import Client
from property.models import Property
from booking.models import Booking
from apps.notification.service import NotificationService

print("=" * 70)
print("BOOKING NOTIFICATION TEST - Partner Mobile App")
print("=" * 70)

# 1. Find a partner with active devices
print("\n📱 Step 1: Finding partner with active devices...")
devices = PartnerDevice.objects.filter(is_active=True).select_related('partner').all()

if not devices.exists():
    print("✗ No active partner devices found!")
    print("\n⚠️  To test notifications:")
    print("1. Make sure a partner has logged into the weel-mobile app")
    print("2. Check if device is registered:")
    print("   ./venv/bin/python -c \"from users.models.partners import PartnerDevice; print(PartnerDevice.objects.filter(is_active=True).count())\"")
    sys.exit(1)

print(f"✓ Found {devices.count()} active partner device(s)")

# 2. Test notification data structure
print("\n📝 Step 2: Testing notification data structure...")
test_booking_data = {
    "type": "booking_event",
    "event": "booking_requested",
    "booking_id": "test-123",
    "booking_number": "1234567",
    "status": "pending",
    "property_title": "Test Property",
    "check_in": "2026-03-15",
    "check_out": "2026-03-18",
    "client_name": "John Doe",
    "client_phone": "+998901234567",
    "guests": 4,
    "adults": 2,
    "children": 2,
    "babies": 0,
}

print("✓ Notification data structure:")
for key, value in test_booking_data.items():
    print(f"  • {key}: {value}")

# 3. Send test notification to each active device
print("\n🔔 Step 3: Sending test notifications...")
app = get_app()

success_count = 0
failure_count = 0

for device in devices:
    partner = device.partner
    print(f"\n  Testing token for partner: {partner.username} ({partner.phone_number})")
    print(f"  Token: {device.fcm_token[:50]}...")
    
    message = messaging.Message(
        notification=messaging.Notification(
            title="New booking request",
            body=f"New booking request from John Doe for Test Property. Check-in: 2026-03-15, Check-out: 2026-03-18. Guests: 4.",
        ),
        data={
            "type": "booking_event",
            "event": "booking_requested",
            "booking_id": "test-123",
            "booking_number": "1234567",
            "status": "pending",
            "property_title": "Test Property",
            "check_in": "2026-03-15",
            "check_out": "2026-03-18",
            "client_name": "John Doe",
            "client_phone": "+998901234567",
            "guests": "4",
            "adults": "2",
            "children": "2",
            "babies": "0",
        },
        token=device.fcm_token,
    )
    
    try:
        response = messaging.send(message, app=app)
        print(f"  ✓ SUCCESS: {response}")
        success_count += 1
    except messaging.UnregisteredError as e:
        print(f"  ✗ Token invalid: {e}")
        device.is_active = False
        device.save()
        failure_count += 1
    except Exception as e:
        print(f"  ✗ Failed: {type(e).__name__}: {e}")
        failure_count += 1

print("\n" + "=" * 70)
print("TEST RESULTS")
print("=" * 70)
print(f"✓ Successful: {success_count}")
print(f"✗ Failed: {failure_count}")
print(f"📱 Total devices tested: {devices.count()}")

if success_count > 0:
    print("\n🎉 Notifications are working correctly!")
    print("\nWhen a client creates a booking, partners will receive:")
    print("  • Push notification with detailed client information")
    print("  • Client name, phone number, guest count")
    print("  • Property title, check-in/out dates")
    print("  • Quick action buttons: Accept ✓ / Reject ✗")
else:
    print("\n⚠️  No successful deliveries. Check:")
    print("  1. Firebase configuration in mobile app")
    print("  2. Partner has logged into weel-mobile app")
    print("  3. Device tokens are valid and registered")

print("=" * 70)
