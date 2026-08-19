from django.contrib.auth import logout
from django.shortcuts import redirect, render


def index(request):
    if request.user.is_authenticated:
        return redirect('applications:dashboard')
    return render(request, 'base/index.html')

def logout_view(request):
    logout(request)
    return redirect('index')
