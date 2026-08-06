import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import SMSMessage, SystemSettings
from .radiusdesk_api import RADIUSdeskAPI
from .models import HotspotPlan
from django.utils import timezone

@csrf_exempt
def gammu_incoming_sms(request):
    """HTTP Webhook endpoint invoked by Gammu's RunOnReceive script."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    # Security Token Check
    secret = request.POST.get('secret')
    if secret != getattr(settings, 'GAMMU_WEBHOOK_SECRET', 'secret_key'):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    sender = request.POST.get('sender')
    text = request.POST.get('text')

    if not sender or not text:
        return JsonResponse({'error': 'Missing sender or text'}, status=400)

    system_settings = SystemSettings.get_singleton()
    if not system_settings.is_sender_allowed(sender):
        return JsonResponse({'error': 'Sender is not permitted'}, status=403)

    # Save to Database Queue
    sms = SMSMessage.objects.create(
        sender_phone=sender,
        raw_text=text,
        status='PENDING'
    )

    # Automatically trigger immediate processing
    process_single_sms(sms)

    return JsonResponse({
        'status': 'success',
        'sms_id': sms.id,
        'processing_status': sms.status
    })

def process_single_sms(sms):
    settings = SystemSettings.get_singleton()
    ref_pattern = settings.transaction_ref_regex or SystemSettings.DEFAULT_TRANSACTION_REF_REGEX
    amount_pattern = settings.amount_regex or SystemSettings.DEFAULT_AMOUNT_REGEX

    # 1. Regex match for Txn ID and Amount
    ref_match = re.search(ref_pattern, sms.raw_text, re.IGNORECASE)
    amt_match = re.search(amount_pattern, sms.raw_text, re.IGNORECASE)

    if not ref_match or not amt_match:
        sms.status = 'INVALID'
        sms.error_message = "Could not parse reference code or amount from SMS."
        sms.save()
        return

    sms.transaction_ref = ref_match.group(1).strip()
    sms.amount = float(amt_match.group(1).replace(',', ''))

    # Prevent duplicates
    if SMSMessage.objects.filter(transaction_ref=sms.transaction_ref).exclude(id=sms.id).exists():
        sms.status = 'INVALID'
        sms.error_message = f"Duplicate transaction reference: {sms.transaction_ref}"
        sms.save()
        return

    # 2. Match Amount to Hotspot Plan
    plan = HotspotPlan.objects.filter(price=sms.amount, is_active=True).first()
    if not plan:
        sms.status = 'FAILED'
        sms.error_message = f"No active plan configured for amount: {sms.amount} UGX"
        sms.save()
        return

    # 3. Use Transaction ID as Username/Voucher
    wifi_username = sms.transaction_ref
    wifi_password = sms.transaction_ref

    # 4. Call RADIUSdesk API with plan-specific IDs
    rd_api = RADIUSdeskAPI()
    success, response = rd_api.create_voucher(
        voucher_code=wifi_username,
        profile_id=plan.radiusdesk_profile_id,
        realm_id=plan.radiusdesk_realm_id,
        cloud_id=plan.radiusdesk_cloud_id,
        owner_id=plan.radiusdesk_owner_id
    )

    if success:
        sms.status = 'PROCESSED'
        sms.radiusdesk_username = wifi_username
        sms.processed_at = timezone.now()
        sms.save()
    else:
        sms.status = 'FAILED'
        sms.error_message = f"RADIUSdesk Error: {response}"
        sms.save()