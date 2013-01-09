# -*- coding: utf-8 -*-

'''

'''


import logging
import json

import requests
from requests.auth import HTTPBasicAuth

from .utils import OAuth2, build_mms_body, parse_mms_body, xml_to_dict, sanitize
from .exceptions import APIError, AccessTokenError, ContentTypeError


log = logging.getLogger(__name__)


class BaseApi(object):
    '''
    classdocs
    '''

    _PATHS = {
        'smsoutbound': 'sms/v2/smsoutbound',
        'smsinbound': 'sms/v2/smsinbound',
        'mmsoutbound': 'mms/v2/mmsoutbound',
        'mmsinbound': 'mms/v2/mmsinbound',
    }

    # session is a class attribute so the connection pool is shared among all instances of BaseApi class
    # and its subclasses (Api and PartnerApi).
    # Note that each Api or PartnerApi instance has its own client_id, client_secret, access token and ssl_client_cert,
    # so each instance deals with a set of credentials, while sharing the connection pool.
    session = requests.Session()
    session.verify = True

    def __init__(self, base_url, client_id, client_secret, access_token=None, ssl_client_cert=None):
        '''
        Constructor
        '''
        self.base_url = base_url
        self.http_ba = HTTPBasicAuth(client_id, client_secret)
        if access_token:
            self.oauth2 = OAuth2(access_token)
        self.ssl_client_cert = ssl_client_cert

    @property
    def client_id(self):
        return self.http_ba.username

    @property
    def client_secret(self):
        return self.http_ba.password

    @property
    def access_token(self):
        try:
            return self.oauth2.access_token
        except AttributeError:
            return None

    @access_token.setter
    def access_token(self, access_token):
        if access_token:
            self.oauth2 = OAuth2(access_token)

    def _make_request(self, url, data=None, attachments=None, url_encoded=False, basic_auth=False):
        '''
        Build the API request and return the formatted result of the API call
        '''

        # Choose the authentication method
        if self.ssl_client_cert:
            auth = self.http_ba
        else:
            try:
                auth = self.http_ba if basic_auth else self.oauth2
            except AttributeError:
                # self.oauth2 has not been set because there is not an access_token
                raise AccessTokenError('Access Token has not been set')

        # Build the request depending on the input parameters
        if not data:
            # GET
            log.info('GETting from URL: {url}'.format(url=url))
            resp = BaseApi.session.get(url=url, auth=auth, cert=self.ssl_client_cert)
        elif isinstance(data, dict):
            # POST
            if not attachments:
                # It's not an MMS
                if not url_encoded:
                    # Simple JSON body
                    headers = {'content-type': 'application/json'}
                    data = json.dumps(data, ensure_ascii=False)
                else:
                    # Data passed to Requests as a dictionary is automatically sent as url encoded
                    # and the proper content-type header is automatically set
                    headers = None
            else:
                # Multipart body (MMS)
                body = build_mms_body(data, attachments)
                data = body.as_string().split('\n\n', 1)[1]  # Skipping MIME headers
                # get_content_type() and get_boundary() don't work until as_string() is called
                headers = {'content-type': body.get_content_type() + '; boundary="' + body.get_boundary() + '"'}

            log.info(('POSTting to URL: {url}\n'
                      '  with body: {body}').format(url=url, body=data))
            resp = BaseApi.session.post(url=url, data=data, headers=headers, auth=auth,
                                        cert=self.ssl_client_cert)
        else:
            raise TypeError("'data' param must be None or a dict")

        log_str = ('Response:\n'
                   '  Status code: {status_code}\n'
                   '  Headers: {headers}\n'
                   '  Body: {body}\n'
                   '  Client id: {client_id}').format(status_code=resp.status_code,
                                                      headers=resp.headers,
                                                      body=resp.content,
                                                      client_id=self.http_ba.username)
        if hasattr(self, 'oauth2'):
            log_str += '\n  Access token: {access_token}'.format(access_token=self.oauth2.access_token)
        log.info(log_str)

        # Process response
        if resp.status_code in (200, 201):
            if resp.headers['content-length'] == '0':
                return None

            content_type = resp.headers['content-type']
            if not content_type:
                raise ContentTypeError("HTTP response does not contain a Content-Type header")

            if content_type.lower().startswith('application/json'):
                return resp.json()
            elif content_type.lower().startswith('multipart/mixed'):
                metadata, attachments = parse_mms_body(content_type, resp.content)
                return metadata, attachments
            else:
                raise ContentTypeError("Unsupported Content-Type '{0}' in HTTP response"
                                       "(only application/json and multipart/mixed are supported".format(content_type))
        elif resp.status_code == 204:
            return None
        else:
            raise APIError(resp)

    def send_sms(self, from_, to, message, callback_url=None):
        url = self.base_url + self._PATHS['smsoutbound']

        # If 'to' contains only digits, it's an MSISDN, else it's an obfuscated identity
        data = {'to': 'tel:+' + to if to.isdigit() else 'alias:' + to,
                'message': message}
        # If 'from_' contains only digits, it's an MSISDN, else it's a sender name
        if from_:
            data['from'] = 'tel:+' + from_ if from_.isdigit() else 'alias:' + from_
        if callback_url:
            data['callbackUrl'] = callback_url

        resp = self._make_request(url, data)

        return resp['id']

    def get_sms_delivery_status(self, sms_id):
        if sms_id.startswith('http://') or sms_id.startswith('https://'):
            url = sms_id + '?fields=to'
        else:
            url = self.base_url + self._PATHS['smsoutbound'] + '/' + sms_id + '?fields=to'

        resp = self._make_request(url)

        return sanitize(resp['to'][0])
#        return [{u'to': to['address'][6:] if to['address'].startswith('alias:') else to['address'][5:],
#                 u'status': to['status']} for to in resp['to']]

    @staticmethod
    def parse_delivery_status(content_type, content):
        if content_type.startswith('application/json'):
            try:
                delivery_status = json.loads(content)
            except ValueError:
                raise ValueError('Bad JSON content')

            return sanitize(delivery_status)
#            delivery_status[u'address'] = delivery_status['address'][6:]\
#                                          if delivery_status['address'].startswith('alias:')\
#                                          else delivery_status['address'][5:]
#            return delivery_status
        else:
            raise ContentTypeError("Unsupported Content-Type '{0}' "
                                   "(only application/json is supported".format(content_type))

    def get_received_sms(self):
        url = self.base_url + self._PATHS['smsinbound']

        resp = self._make_request(url, basic_auth=True)

        if resp:
            return sanitize(resp)
#            return [{u'id': sms['id'],
#                     u'from': sms['from'][6:] if sms['from'].startswith('alias:') else sms['from'][5:],
#                     u'obfuscated': sms['from'].startswith('alias:'),
#                     u'to': sms['to'][5:],
#                     u'message': sms['message'],
#                     u'timestamp': datetime.strptime(sms['timestamp'], '%Y-%m-%dT%H:%M:%S.%f+0000')} for sms in resp]
        else:
            return []

    @staticmethod
    def parse_received_sms(content_type, content):
        if content_type.startswith('application/json'):
            try:
                sms = json.loads(content)
            except ValueError:
                raise ValueError('Bad JSON content')
        elif content_type.startswith('application/xml'):
            try:
                sms = xml_to_dict(content, ('id', 'from', 'to', 'message', 'timestamp'))
            except KeyError:
                raise ValueError('Bad XML content')
        else:
            raise ContentTypeError("Unsupported Content-Type '{0}' "
                                   "(only application/json and application/xml are supported".format(content_type))

        return sanitize(sms)
#        sms[u'obfuscated'] = sms['from'].startswith('alias:')
#        sms[u'from'] = sms['from'][6:] if sms['obfuscated'] else sms['from'][5:]
#        sms[u'to'] = sms['to'][5:]
#        sms[u'timestamp'] = datetime.strptime(sms['timestamp'], '%Y-%m-%dT%H:%M:%S.%f+0000')
#        return sms

    def send_mms(self, from_, to, subject, attachments, callback_url=None):
        # TODO: Test MMS w/o attachments
        url = self.base_url + self._PATHS['mmsoutbound']

        # If 'to' contains only digits, it's an MSISDN, else it's an obfuscated identity
        metadata = {'to': 'tel:+' + to if to.isdigit() else 'alias:' + to,
                    'subject': subject}
        # If 'from_' contains only digits, it's an MSISDN, else it's a sender name
        if from_:
            metadata['from'] = 'tel:+' + from_ if from_.isdigit() else 'alias:' + from_
        if callback_url:
            metadata['callbackUrl'] = callback_url

        resp = self._make_request(url, metadata, attachments)

        return resp['id']

    def get_mms_delivery_status(self, mms_id):
        if mms_id.startswith('http://') or mms_id.startswith('https://'):
            url = mms_id + '?fields=to'
        else:
            url = self.base_url + self._PATHS['mmsoutbound'] + '/' + mms_id + '?fields=to'

        resp = self._make_request(url)

        return sanitize(resp['to'][0])
#        return [{u'to': to['address'][6:] if to['address'].startswith('alias:') else to['address'][5:],
#                 u'status': to['status']} for to in resp['to']]

    def get_received_mms(self):
        url = self.base_url + self._PATHS['mmsinbound']

        resp = self._make_request(url, basic_auth=True)

        if resp:
            return [mms['id'] for mms in resp]
        else:
            return []

    def get_received_mms_details(self, mms_id):
        # TODO: Test MMS w/o attachments
        url = self.base_url + self._PATHS['mmsinbound'] + '/' + mms_id

        metadata, attachments = self._make_request(url, basic_auth=True)

        mms = sanitize(metadata)
        mms[u'attachments'] = attachments
        return mms
#        return {u'id': metadata['id'],
#                u'from': metadata['from'][6:] if metadata['from'].startswith('alias:')
#                         else metadata['from'][5:],
#                u'obfuscated': metadata['from'].startswith('alias:'),
#                u'to': metadata['to'][5:],
#                u'subject': metadata['subject'],
#                u'timestamp': datetime.strptime(metadata['timestamp'], '%Y-%m-%dT%H:%M:%S.%f+0000'),
#                u'attachments': attachments}

    @staticmethod
    def parse_received_mms(content_type, content):
        metadata, attachments = parse_mms_body(content_type, content)

        mms = sanitize(metadata)
        mms[u'attachments'] = attachments
        return mms
#        return {u'id': metadata['id'],
#                u'from': metadata['from'][6:] if metadata['from'].startswith('alias:')
#                         else metadata['from'][5:],
#                u'obfuscated': metadata['from'].startswith('alias:'),
#                u'to': metadata['to'][5:],
#                u'subject': metadata['subject'],
#                u'timestamp': datetime.strptime(metadata['timestamp'], '%Y-%m-%dT%H:%M:%S.%f+0000'),
#                u'attachments': attachments}