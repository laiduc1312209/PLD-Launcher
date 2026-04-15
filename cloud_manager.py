"""
PLD Launcher — Backblaze B2 Cloud Manager (No boto3 — uses requests + S3 API)
Handles file synchronization using S3-compatible REST API with AWS Signature V4.
"""
import os
import hashlib
import hmac
import datetime
import requests
from xml.etree import ElementTree
from config import B2_KEY_ID, B2_APPLICATION_KEY, B2_ENDPOINT, B2_BUCKET_NAME


class CloudManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CloudManager, cls).__new__(cls)
            cls._instance.endpoint = f"https://{B2_ENDPOINT}"
            cls._instance.region = B2_ENDPOINT.split('.')[1]  # e.g. "eu-central-003"
            cls._instance.access_key = B2_KEY_ID
            cls._instance.secret_key = B2_APPLICATION_KEY
            cls._instance.bucket = B2_BUCKET_NAME
        return cls._instance

    # ── AWS Signature V4 ─────────────────────────────────────────

    def _sign(self, key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp):
        k_date = self._sign(('AWS4' + self.secret_key).encode('utf-8'), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, 's3')
        k_signing = self._sign(k_service, 'aws4_request')
        return k_signing

    def _make_headers(self, method, object_key, payload=b'', content_type=''):
        now = datetime.datetime.utcnow()
        date_stamp = now.strftime('%Y%m%d')
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')

        host = B2_ENDPOINT
        canonical_uri = f'/{self.bucket}/{object_key}'
        canonical_querystring = ''
        payload_hash = hashlib.sha256(payload).hexdigest()

        headers_to_sign = {
            'host': host,
            'x-amz-content-sha256': payload_hash,
            'x-amz-date': amz_date,
        }
        if content_type:
            headers_to_sign['content-type'] = content_type

        signed_header_keys = sorted(headers_to_sign.keys())
        signed_headers_str = ';'.join(signed_header_keys)
        canonical_headers = ''.join(f'{k}:{headers_to_sign[k]}\n' for k in signed_header_keys)

        canonical_request = '\n'.join([
            method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers_str, payload_hash
        ])

        credential_scope = f'{date_stamp}/{self.region}/s3/aws4_request'
        string_to_sign = '\n'.join([
            'AWS4-HMAC-SHA256', amz_date, credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        ])

        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        auth_header = (
            f'AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, '
            f'SignedHeaders={signed_headers_str}, Signature={signature}'
        )

        result_headers = {
            'x-amz-date': amz_date,
            'x-amz-content-sha256': payload_hash,
            'Authorization': auth_header,
        }
        if content_type:
            result_headers['Content-Type'] = content_type

        return result_headers

    # ── Public API ───────────────────────────────────────────────

    def upload_file(self, local_path, cloud_filename):
        """Uploads a file to Backblaze B2."""
        if self.access_key == "YOUR_KEY_ID":
            return False, "Chưa cấu hình Backblaze B2 Key ID."

        try:
            with open(local_path, 'rb') as f:
                payload = f.read()

            headers = self._make_headers('PUT', cloud_filename, payload, 'application/octet-stream')
            url = f"{self.endpoint}/{self.bucket}/{cloud_filename}"
            resp = requests.put(url, headers=headers, data=payload, timeout=60)

            if resp.status_code in (200, 201):
                return True, "Upload thành công."
            else:
                return False, f"B2 Upload Error: {resp.status_code} - {resp.text}"
        except Exception as e:
            return False, f"B2 Upload Error: {str(e)}"

    def download_file(self, cloud_filename, dest_path):
        """Downloads a file from Backblaze B2."""
        if self.access_key == "YOUR_KEY_ID":
            return False, "Chưa cấu hình Backblaze B2 Key ID."

        try:
            headers = self._make_headers('GET', cloud_filename)
            url = f"{self.endpoint}/{self.bucket}/{cloud_filename}"
            resp = requests.get(url, headers=headers, timeout=60)

            if resp.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, 'wb') as f:
                    f.write(resp.content)
                return True, "Download thành công."
            elif resp.status_code == 404:
                return False, "File không tồn tại trên cloud."
            else:
                return False, f"B2 Download Error: {resp.status_code} - {resp.text}"
        except Exception as e:
            return False, f"B2 Download Error: {str(e)}"

    def list_files(self):
        """Lists files in the bucket."""
        try:
            headers = self._make_headers('GET', '')
            url = f"{self.endpoint}/{self.bucket}"
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 200:
                root = ElementTree.fromstring(resp.text)
                ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
                return [
                    content.find('s3:Key', ns).text
                    for content in root.findall('.//s3:Contents', ns)
                    if content.find('s3:Key', ns) is not None
                ]
            return []
        except:
            return []
