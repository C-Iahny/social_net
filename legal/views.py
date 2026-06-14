from django.shortcuts import render

def cgu_view(request):
    return render(request, 'legal/cgu.html')

def confidentialite_view(request):
    return render(request, 'legal/confidentialite.html')
