from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import CustomUser
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.middleware.csrf import get_token
from django.db.models import Q
import json
from eventos.models import Evento, EventoUserResult
from django.db import transaction
import logging

logger = logging.getLogger('accounts')

@api_view(['POST'])
def register_user(request):
    data = request.data
    user_id = data.get('user_id')
    password = data.get('password')
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    fecha_nacimiento = data.get('fecha_nacimiento')
    numero_celular = data.get('numero_celular')
    direccion = data.get('direccion')

    if CustomUser.objects.filter(user_id=user_id).exists():
        return Response({'error': 'User ID already exists'}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.create(
        user_id=user_id,
        password=make_password(password),
        nombre=nombre,
        apellido=apellido,
        fecha_nacimiento=fecha_nacimiento,
        numero_celular=numero_celular,
        direccion=direccion,
    )
    user.save()
    return Response({'message': 'User created successfully'}, status=status.HTTP_201_CREATED)

@csrf_exempt
@api_view(['POST'])
def login_user(request):
    data = request.data
    user_id = data.get('user_id')
    password = data.get('password')

    user = authenticate(request, username=user_id, password=password)
    if user is not None:
        return JsonResponse({"message": "Login successful", "user_id": user.user_id}, status=status.HTTP_200_OK)
    else:
        return JsonResponse({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html')

@login_required
def manage_users(request):
    search_query = request.GET.get('search', '')  # Get the search query from the request
    users = CustomUser.objects.all()

    # Filter users based on search query
    if search_query:
        users = users.filter(
            Q(user_id__icontains=search_query) |  # Match user_id
            Q(numero_celular__icontains=search_query)  # Match phone number
        )

    return render(request, 'accounts/manage_users.html', {'users': users})
@login_required
def update_tickets(request, user_id):
    user = get_object_or_404(CustomUser, user_id=user_id)

    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'add':
            user.event_tickets += 1
            messages.success(request, f"Added 1 ticket for {user.nombre}.")
        elif action == 'subtract' and user.event_tickets > 0:
            user.event_tickets -= 1
            messages.success(request, f"Subtracted 1 ticket from {user.nombre}.")
        else:
            messages.warning(request, f"{user.nombre} has no tickets to subtract.")

        user.save()

    return redirect('accounts:manage_users')  # Updated with namespace
def get_user_tickets(request):
    user_id = request.GET.get('user_id')
    try:
        user = CustomUser.objects.get(user_id=user_id)
        data = {'event_tickets': user.event_tickets}
        return JsonResponse(data, status=200)
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@csrf_exempt
def use_ticket(request):
    """
    Use a ticket to participate in an event.
    This creates the participation record (EventoUserResult).
    User can then submit/update predictions unlimited times.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            event_id = data.get('event_id')

            if not all([user_id, event_id]):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)

            user = CustomUser.objects.get(user_id=user_id)
            evento = Evento.objects.get(id=event_id, current=True)

            # Check if user has tickets
            if user.event_tickets < 1:
                return JsonResponse({'error': 'No tienes tickets disponibles'}, status=400)

            # Check if already participated
            if EventoUserResult.objects.filter(user=user, evento=evento).exists():
                return JsonResponse({'error': 'Ya has participado en este evento'}, status=400)

            # Use ticket and create participation
            with transaction.atomic():
                user.event_tickets -= 1
                user.save()

                EventoUserResult.objects.create(
                    user=user,
                    evento=evento,
                    total_points=0
                )

            return JsonResponse({
                'success': True,
                'message': 'Ticket usado exitosamente',
                'remaining_tickets': user.event_tickets
            }, status=200)

        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Evento no encontrado o no está activo'}, status=404)
        except Exception as e:
            logger.error(f"Error using ticket: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método inválido'}, status=405)

def csrf_token_view(request):
    return JsonResponse({'csrfToken': get_token(request)})


@login_required
def delete_user(request, user_id):
    """Delete a user from the system"""
    if request.method == "POST":
        try:
            user = get_object_or_404(CustomUser, user_id=user_id)
            user_name = f"{user.nombre} {user.apellido}" if user.nombre else user.user_id
            user.delete()
            messages.success(request, f"Usuario {user_name} eliminado exitosamente")
        except Exception as e:
            messages.error(request, f"Error al eliminar usuario: {str(e)}")

        return redirect('accounts:manage_users')

    return redirect('accounts:manage_users')

