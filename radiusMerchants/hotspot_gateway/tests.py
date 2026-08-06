import re
from unittest.mock import MagicMock, patch

from django.test import TestCase

from hotspot_gateway.models import SystemSettings
from hotspot_gateway.radiusdesk_api import RADIUSdeskAPI


class SystemSettingsTests(TestCase):
    def test_allowed_sender_ids_are_parsed_and_checked(self):
        settings = SystemSettings.get_singleton()
        settings.allowed_sender_ids = '256700000000, 256700000001'
        settings.save()

        self.assertTrue(settings.is_sender_allowed('256700000000'))
        self.assertTrue(settings.is_sender_allowed('256700000001'))
        self.assertFalse(settings.is_sender_allowed('256700000099'))

    def test_admin_ips_are_parsed_and_checked(self):
        settings = SystemSettings.get_singleton()
        settings.admin_allowed_ips = '127.0.0.1, ::1'
        settings.save()

        self.assertTrue(settings.is_admin_ip_allowed('127.0.0.1'))
        self.assertTrue(settings.is_admin_ip_allowed('::1'))
        self.assertFalse(settings.is_admin_ip_allowed('10.0.0.5'))

    def test_sms_regex_fields_are_customizable(self):
        settings = SystemSettings.get_singleton()
        settings.transaction_ref_regex = r'Ref\s*[:=]\s*([A-Z0-9]+)'
        settings.amount_regex = r'Amount\s*[:=]\s*UGX\s*([\d,]+)'
        settings.save()

        message = 'Ref: ABC123 Amount: UGX 2,500'

        ref_match = re.search(settings.transaction_ref_regex, message, re.IGNORECASE)
        amount_match = re.search(settings.amount_regex, message, re.IGNORECASE)

        self.assertIsNotNone(ref_match)
        self.assertEqual(ref_match.group(1), 'ABC123')
        self.assertIsNotNone(amount_match)
        self.assertEqual(amount_match.group(1), '2,500')

    def test_system_settings_singleton_is_created_for_admin(self):
        SystemSettings.objects.all().delete()

        settings = SystemSettings.get_singleton()

        self.assertIsNotNone(settings.pk)
        self.assertTrue(SystemSettings.objects.filter(pk=settings.pk).exists())


class RadiusDeskAPITests(TestCase):
    def test_create_voucher_uses_transaction_id_as_single_field_voucher(self):
        api = RADIUSdeskAPI()
        api.token = 'demo-token'

        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True, 'data': {'id': 1}}

        with patch('hotspot_gateway.radiusdesk_api.requests.post', return_value=mock_response) as mock_post:
            success, response = api.create_voucher(
                voucher_code='TXN12345',
                profile_id=46,
                realm_id=19,
                cloud_id=23,
                owner_id=31,
                extra_value='TXN12345',
            )

        self.assertTrue(success)
        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(payload['single_field'], 'true')
        self.assertEqual(payload['username'], 'TXN12345')
        self.assertEqual(payload['password'], 'TXN12345')
        self.assertEqual(payload['profile_id'], 46)
        self.assertEqual(payload['realm_id'], 19)
        self.assertEqual(payload['cloud_id'], 23)
        self.assertEqual(payload['name'], 'TXN12345')
        self.assertEqual(payload['extra_name'], 'transaction_ref')
        self.assertEqual(payload['extra_value'], 'TXN12345')
