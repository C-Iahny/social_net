from django.test import TestCase

# ATTENTION — ce fichier contenait auparavant un script exécuté à l'import :
# une clé API Africa's Talking en clair, un numéro de téléphone réel, et un
# envoi de SMS effectif. Il partait donc à chaque `manage.py test` et la clé
# était publiée dans l'historique Git.
#
# Pour tester manuellement l'envoi de SMS, utiliser la commande shell avec les
# identifiants pris dans l'environnement :
#     python manage.py shell -c "from account.sms import send_otp_sms; send_otp_sms('+261XXXXXXXXX', '123456')"
