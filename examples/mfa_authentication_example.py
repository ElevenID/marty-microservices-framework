"""
Multi-Factor Authentication (MFA) Example.

This example demonstrates how to use the MFA system including:
- TOTP device registration and verification
- SMS and Email MFA (stub implementations)
- Challenge creation and verification
- Backup codes management
"""

import asyncio
import traceback
from datetime import datetime, timezone

from mmf_new.services.identity.application.ports_out.authentication_provider import (
    AuthenticationContext,
)
from mmf_new.services.identity.domain.models.mfa import (
    MFADeviceType,
    MFAMethod,
    MFAVerification,
)
from mmf_new.services.identity.infrastructure.adapters.mfa import (
    EmailMFAAdapter,
    EmailMFAConfig,
    SMSMFAAdapter,
    SMSMFAConfig,
    TOTPAdapter,
    TOTPConfig,
)


async def demonstrate_totp_workflow():
    """Demonstrate complete TOTP workflow."""
    print("=== TOTP Workflow Demonstration ===")

    # Configure TOTP provider
    totp_config = TOTPConfig(
        issuer="Demo MMF Service",
        period=30,
        digits=6,
        window=1
    )
    totp_provider = TOTPAdapter(totp_config)

    # Create authentication context
    context = AuthenticationContext(
        client_ip="192.168.1.100",
        user_agent="Demo Client",
        timestamp=datetime.now(timezone.utc)
    )

    # User registration flow
    user_id = "demo_user_123"

    print(f"1. Registering TOTP device for user: {user_id}")

    # Register TOTP device
    device = await totp_provider.register_device(
        user_id=user_id,
        device_type=MFADeviceType.TOTP_APP,
        device_name="Google Authenticator",
        device_data={},  # Secret will be auto-generated
        context=context
    )

    print(f"   Device registered: {device.device_id}")
    print(f"   Device status: {device.status.value}")

    # Get device secret and QR code URL
    secret = device.device_data["secret"]
    qr_url = await totp_provider.generate_qr_code_url(
        secret=secret,
        user_identifier="demo@example.com",
        issuer=totp_config.issuer
    )

    print(f"   TOTP Secret: {secret}")
    print(f"   QR Code URL: {qr_url}")

    # Generate a TOTP code for verification (simulating user input)
    print(f"\n2. Simulating TOTP code generation...")
    current_code = totp_provider._generate_totp_code(secret, int(asyncio.get_event_loop().time()) // 30)
    print(f"   Generated TOTP code: {current_code}")

    # Verify device with TOTP code
    print(f"\n3. Verifying device with TOTP code...")
    verified_device = await totp_provider.verify_device(
        device_id=device.device_id,
        verification_code=current_code,
        context=context
    )

    print(f"   Device verified: {verified_device.status.value}")
    print(f"   Verification time: {verified_device.verified_at}")

    # Create MFA challenge
    print(f"\n4. Creating MFA challenge...")
    challenge = await totp_provider.create_challenge(
        user_id=user_id,
        method=MFAMethod.TOTP,
        device_id=device.device_id,
        context=context
    )

    print(f"   Challenge created: {challenge.challenge_id}")
    print(f"   Challenge expires: {challenge.expires_at}")

    # Generate new TOTP code for verification
    verification_code = totp_provider._generate_totp_code(secret, int(asyncio.get_event_loop().time()) // 30)
    print(f"   New TOTP code: {verification_code}")

    # Verify challenge
    print(f"\n5. Verifying MFA challenge...")
    verification = MFAVerification.with_verification_code(
        challenge_id=challenge.challenge_id,
        device_id=device.device_id,
        verification_code=verification_code
    )

    verification_response = await totp_provider.verify_challenge(verification, context)

    print(f"   Verification success: {verification_response.success}")
    if verification_response.success:
        print(f"   Verification method: {verification_response.metadata.get('method')}")
    else:
        print(f"   Verification error: {verification_response.error_message}")

    # Generate and test backup codes
    print(f"\n6. Managing backup codes...")
    backup_codes = await totp_provider.generate_backup_codes(user_id, count=5, context=context)
    print(f"   Generated backup codes: {backup_codes}")

    # Test backup code verification
    test_backup_code = backup_codes[0]
    backup_verification = MFAVerification.with_backup_code(
        challenge_id=challenge.challenge_id,
        backup_code=test_backup_code
    )

    # Create new challenge for backup code test
    backup_challenge = await totp_provider.create_challenge(
        user_id=user_id,
        method=MFAMethod.TOTP,
        context=context
    )

    backup_verification = MFAVerification.with_backup_code(
        challenge_id=backup_challenge.challenge_id,
        backup_code=test_backup_code
    )

    backup_response = await totp_provider.verify_challenge(backup_verification, context)
    print(f"   Backup code verification success: {backup_response.success}")

    # Verify backup code is consumed (can't be used again)
    is_valid_again = await totp_provider.verify_backup_code(user_id, test_backup_code, context)
    print(f"   Backup code reuse (should be False): {is_valid_again}")

    print(f"\n   TOTP demonstration completed successfully!")


async def demonstrate_sms_workflow():
    """Demonstrate SMS MFA workflow (stub)."""
    print("\n=== SMS MFA Workflow Demonstration ===")

    # Configure SMS provider
    sms_config = SMSMFAConfig(
        code_length=6,
        code_expiry_minutes=5
    )
    sms_provider = SMSMFAAdapter(sms_config)

    context = AuthenticationContext(
        client_ip="192.168.1.101",
        user_agent="Demo Mobile Client"
    )

    user_id = "demo_user_456"

    print(f"1. Registering SMS device for user: {user_id}")

    # Register SMS device
    sms_device = await sms_provider.register_device(
        user_id=user_id,
        device_type=MFADeviceType.SMS_PHONE,
        device_name="Personal Phone",
        device_data={"phone_number": "+1234567890"},
        context=context
    )

    print(f"   SMS device registered: {sms_device.device_id}")

    # Create SMS challenge
    print(f"\n2. Creating SMS challenge...")
    sms_challenge = await sms_provider.create_challenge(
        user_id=user_id,
        method=MFAMethod.SMS,
        device_id=sms_device.device_id,
        context=context
    )

    print(f"   SMS challenge created: {sms_challenge.challenge_id}")

    # In the stub implementation, the SMS code is stored internally
    # In production, the user would receive the code via SMS
    sent_code = sms_provider._sent_codes.get(sms_challenge.challenge_id)
    print(f"   SMS code sent (stub): {sent_code}")

    # Verify SMS challenge
    print(f"\n3. Verifying SMS challenge...")
    sms_verification = MFAVerification.with_verification_code(
        challenge_id=sms_challenge.challenge_id,
        device_id=sms_device.device_id,
        verification_code=sent_code
    )

    sms_response = await sms_provider.verify_challenge(sms_verification, context)
    print(f"   SMS verification success: {sms_response.success}")

    print(f"\n   SMS demonstration completed!")


async def demonstrate_email_workflow():
    """Demonstrate Email MFA workflow (stub)."""
    print("\n=== Email MFA Workflow Demonstration ===")

    # Configure Email provider
    email_config = EmailMFAConfig(
        code_length=8,
        code_expiry_minutes=10
    )
    email_provider = EmailMFAAdapter(email_config)

    context = AuthenticationContext(
        client_ip="192.168.1.102",
        user_agent="Demo Web Client"
    )

    user_id = "demo_user_789"

    print(f"1. Registering Email device for user: {user_id}")

    # Register Email device
    email_device = await email_provider.register_device(
        user_id=user_id,
        device_type=MFADeviceType.EMAIL,
        device_name="Primary Email",
        device_data={"email_address": "demo@example.com"},
        context=context
    )

    print(f"   Email device registered: {email_device.device_id}")

    # Create Email challenge
    print(f"\n2. Creating Email challenge...")
    email_challenge = await email_provider.create_challenge(
        user_id=user_id,
        method=MFAMethod.EMAIL,
        device_id=email_device.device_id,
        context=context
    )

    print(f"   Email challenge created: {email_challenge.challenge_id}")

    # In the stub implementation, the email code is stored internally
    sent_code = email_provider._sent_codes.get(email_challenge.challenge_id)
    print(f"   Email code sent (stub): {sent_code}")

    # Verify Email challenge
    print(f"\n3. Verifying Email challenge...")
    email_verification = MFAVerification.with_verification_code(
        challenge_id=email_challenge.challenge_id,
        device_id=email_device.device_id,
        verification_code=sent_code
    )

    email_response = await email_provider.verify_challenge(email_verification, context)
    print(f"   Email verification success: {email_response.success}")

    print(f"\n   Email demonstration completed!")


async def demonstrate_device_management():
    """Demonstrate device management features."""
    print("\n=== Device Management Demonstration ===")

    totp_config = TOTPConfig()
    totp_provider = TOTPAdapter(totp_config)

    user_id = "demo_user_mgmt"

    # Register multiple devices
    print(f"1. Registering multiple devices for user: {user_id}")

    devices = []
    device_names = ["Google Authenticator", "Authy", "Microsoft Authenticator"]

    for i, name in enumerate(device_names):
        device = await totp_provider.register_device(
            user_id=user_id,
            device_type=MFADeviceType.TOTP_APP,
            device_name=name,
            device_data={}
        )
        devices.append(device)
        print(f"   Registered device {i+1}: {device.device_name} ({device.device_id})")

    # List user devices
    print(f"\n2. Listing user devices...")
    user_devices = await totp_provider.get_user_devices(user_id, include_inactive=True)
    print(f"   Total devices for user: {len(user_devices)}")

    for device in user_devices:
        print(f"   - {device.device_name}: {device.status.value} ({device.device_id})")

    # Update device name
    print(f"\n3. Updating device name...")
    updated_device = await totp_provider.update_device(
        device_id=devices[0].device_id,
        device_name="Primary Authenticator"
    )
    print(f"   Updated device name: {updated_device.device_name}")

    # Revoke a device
    print(f"\n4. Revoking a device...")
    revoked = await totp_provider.revoke_device(devices[1].device_id)
    print(f"   Device revoked: {revoked}")

    # List active devices only
    print(f"\n5. Listing active devices...")
    active_devices = await totp_provider.get_user_devices(user_id, include_inactive=False)
    print(f"   Active devices: {len(active_devices)}")

    for device in active_devices:
        print(f"   - {device.device_name}: {device.status.value}")

    print(f"\n   Device management demonstration completed!")


async def main():
    """Run all MFA demonstrations."""
    print("Multi-Factor Authentication (MFA) System Demonstration")
    print("=" * 60)

    try:
        # Demonstrate TOTP workflow
        await demonstrate_totp_workflow()

        # Demonstrate SMS workflow (stub)
        await demonstrate_sms_workflow()

        # Demonstrate Email workflow (stub)
        await demonstrate_email_workflow()

        # Demonstrate device management
        await demonstrate_device_management()

        print(f"\n" + "=" * 60)
        print("All MFA demonstrations completed successfully!")
        print("\nKey features demonstrated:")
        print("- TOTP device registration and verification")
        print("- QR code URL generation for authenticator apps")
        print("- MFA challenge creation and verification")
        print("- Backup codes generation and consumption")
        print("- SMS and Email MFA (stub implementations)")
        print("- Device management (register, update, revoke)")
        print("- Rate limiting and security controls")

    except Exception as e:
        print(f"Error during demonstration: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
