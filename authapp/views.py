from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('accounts:dashboard')  # Redirect to the dashboard
        else:
            return render(request, 'authapp/login.html', {'error': 'Invalid username or password'})
    return render(request, 'authapp/login.html')



def logout_view(request):
    logout(request)
    return redirect('/auth/login/')
