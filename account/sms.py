"""
account/sms.py
──────────────
Backend SMS pour Vazimba — vérification de numéro de téléphone.

Fournisseur principal : Africa's Talking (couverture Madagascar : Airtel, Orange, Telma)
Backend développement : console (affiche le SMS dans le terminal, aucun envoi réel)

Normalisation des numéros malgaches :
  034 XX XXX XX  →  +26134XXXXXXX
  032 XX XXX XX  →  +26132XXXXXXX
  Formats acceptés : 034..., 0034..., +261 34..., 261 34...
"""

import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation du numéro de téléphone
# ─────────────────────────────────────────────────────────────────────────────

_MADAGASCAR_PREFIXES = ('32', '33', '34', '38', '20')


def normalize_madagascar_phone(raw: str) -> str | None:
    """
    Convertit un numéro saisi librement en format E.164 (+261XXXXXXXXX).
    Retourne None si le numéro n'est pas reconnaissable.

    Exemples acceptés :
        034 12 345 67  →  +261341234567
        0341234567     →  +261341234567
        +261 34 12 345 67  →  +261341234567
        261341234567   →  +261341234567
    """
    if not raw:
        return None

    # Supprimer espaces, tirets, points, parenthèses
    digits = re.sub(r'[\s\-\.\(\)]', '', raw)

    # Supprimer le + initial si présent
    if digits.startswith('+'):
        digits = digits[1:]

    # Forme internationale : 261XXXXXXXXX (12 chiffres)
    if digits.startswith('261') and len(digits) == 12:
        local = digits[3:]  # les 9 chiffres après 261
        prefix2 = local[:2]
        if prefix2 in _MADAGASCAR_PREFIXES:
            return '+' + digits

    # Forme locale commençant par 0 : 0XXXXXXXXX (10 chiffres)
    if digits.startswith('0') and len(digits) == 10:
        local = digits[1:]  # sans le 0 initial
        prefix2 = local[:2]
        if prefix2 in _MADAGASCAR_PREFIXES:
            return '+261' + local

    # Forme avec 00 international : 00261XXXXXXXXX (14 chiffres)
    if digits.startswith('00261') and len(digits) == 14:
        local = digits[5:]
        prefix2 = local[:2]
        if prefix2 in _MADAGASCAR_PREFIXES:
            return '+261' + local

    return None


def format_phone_display(e164: str) -> str:
    """
    Formate un numéro E.164 pour l'affichage.
    +261341234567 → +261 34 12 345 67
    """
    if not e164 or not e164.startswith('+261') or len(e164) != 13:
        return e164
    d = e164[4:]   # 9 chiffres
    return f'+261 {d[:2]} {d[2:4]} {d[4:7]} {d[7:]}'


# ─────────────────────────────────────────────────────────────────────────────
# Backends SMS
# ─────────────────────────────────────────────────────────────────────────────

def _send_via_console(to: str, message: str) -> dict:
    """Backend développement : affiche le SMS dans les logs Django."""
    logger.info(
        '\n' + '=' * 60 +
        f'\n[SMS CONSOLE] To: {to}\n{message}\n' +
        '=' * 60
    )
    print(f'\n[SMS] To: {to}\n{message}\n')
    return {'status': 'ok', 'backend': 'console'}


def _send_via_africastalking(to: str, message: str) -> dict:
    """Backend production : Africa's Talking SMS API."""
    try:
        import africastalking
    except ImportError:
        logger.error('[SMS] africastalking non installé — pip install africastalking')
        raise RuntimeError('Package africastalking manquant.')

    username = getattr(settings, 'AT_USERNAME', 'sandbox')
    api_key  = getattr(settings, 'AT_API_KEY',  'atsk_sandbox_key')
    sender   = getattr(settings, 'AT_SENDER',   None)

    africastalking.initialize(username, api_key)
    sms = africastalking.SMS

    kwargs = {'message': message, 'recipients': [to]}
    if sender:
        kwargs['sender_id'] = sender

    response = sms.send(**kwargs)
    logger.info('[SMS] Africa\'s Talking response: %s', response)

    # Vérifier qu'au moins un message est "Success"
    recipients = response.get('SMSMessageData', {}).get('Recipients', [])
    if not recipients:
        raise RuntimeError(f'Africa\'s Talking : aucun destinataire dans la réponse — {response}')

    status = recipients[0].get('status', '')
    if status not in ('Success', 'success'):
        raise RuntimeError(f'Africa\'s Talking : statut inattendu "{status}" — {response}')

    return {'status': 'ok', 'backend': 'africastalking', 'at_response': response}


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ─────────────────────────────────────────────────────────────────────────────

def send_otp_sms(to: str, code: str) -> dict:
    """
    Envoie le code OTP par SMS au numéro `to` (format E.164).
    Sélectionne automatiquement le backend selon SMS_BACKEND dans settings.py.

    Raises:
        RuntimeError: si l'envoi échoue côté fournisseur.
    """
    message = (
        f'Votre code Vazimba : {code}\n'
        f'Valable 10 minutes. Ne le partagez jamais.'
    )

    backend = getattr(settings, 'SMS_BACKEND', 'console')

    if backend == 'africastalking':
        return _send_via_africastalking(to, message)
    else:
        # Fallback console (développement ou backend inconnu)
        return _send_via_console(to, message)
