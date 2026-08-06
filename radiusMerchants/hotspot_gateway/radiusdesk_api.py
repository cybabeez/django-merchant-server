import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class RADIUSdeskAPI:
    def __init__(self):
        self.base_url = getattr(settings, 'RADIUSDESK_URL', 'http://127.0.0.1/cake4/rd_cake')
        self.username = getattr(settings, 'RADIUSDESK_ADMIN_USER', 'root')
        self.password = getattr(settings, 'RADIUSDESK_ADMIN_PASS', 'admin')
        self.token = None

    def authenticate(self):
        """Fetches auth token from RADIUSdesk."""
        url = f"{self.base_url}/dashboard/authenticate.json"
        try:
            res = requests.post(url, json={'username': self.username, 'password': self.password}, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get('success'):
                self.token = data.get('data', {}).get('token')
                return True
        except Exception as e:
            logger.error(f"RADIUSdesk Auth Error: {e}")
        return False

    def create_permanent_user(self, username, password, profile_id, realm_id, cloud_id, owner_id=31):
        """Creates a permanent user using the plan's exact Profile, Realm, Cloud, and Owner IDs."""
        if not self.token and not self.authenticate():
            return False, "Failed to authenticate with RADIUSdesk"

        url = f"{self.base_url}/permanent-users/add.json"
        params = {'token': self.token}
        
        payload = {
            'username': username,
            'password': password,
            'profile_id': profile_id,
            'realm_id': realm_id,
            'cloud_id': cloud_id,
            'user_id': owner_id,
            'active': 1,
            'always_active': 1,
        }

        try:
            res = requests.post(url, params=params, json=payload, timeout=10)
            data = res.json()
            if data.get('success'):
                return True, data
            message = data.get('message') or data.get('errors', 'Failed to create user')
            return False, message
        except Exception as e:
            return False, str(e)

        
    def create_voucher(self, voucher_code, profile_id, realm_id, cloud_id, owner_id=31, password=None, extra_name='transaction_ref', extra_value=None):
        """Creates a single-field voucher where the actual voucher credential is the SMS transaction ID.

        RadiusDesk single-field vouchers use the same username/password value, so we set both to
        the transaction ID and keep the transaction reference as extra metadata for traceability.
        """
        if not self.token and not self.authenticate():
            return False, "Failed to authenticate with RADIUSdesk"

        url = f"{self.base_url}/vouchers/add.json"
        params = {'token': self.token}

        payload = {
            'single_field': 'true',
            'name': voucher_code,
            'password': voucher_code,
            'profile_id': profile_id,
            'realm_id': realm_id,
            'cloud_id': cloud_id,
            'user_id': owner_id,
            'status': 'new',
            'activate_on_login': 1,
        }

        # Label the voucher with the transaction ID so it is visible in RadiusDesk.
        payload['name'] = voucher_code

        if extra_name and extra_value is not None:
            payload['extra_name'] = extra_name
            payload['extra_value'] = extra_value

        try:
            res = requests.post(url, params=params, json=payload, timeout=10)
            data = res.json()
            if data.get('success'):
                return True, data

            message = data.get('message') or data.get('errors', 'Failed to create voucher')
            return False, message
        except Exception as e:
            return False, str(e)
        