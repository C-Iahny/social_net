import africastalking

africastalking.initialize('sandbox', 'atsk_c7b5444a88a7181bfeb549cc18ab907214e7db5ea6ba5719260e98a2f5e9785b77ad1bb1')
sms = africastalking.SMS
r = sms.send(message='Code Vazimba test : 123456', recipients=['+261335289957'])
print(r)