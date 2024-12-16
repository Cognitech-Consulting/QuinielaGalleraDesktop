from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from .models import Evento, Ronda, Pelea, Prediccion
from .forms import EventoForm
from django.views.decorators.csrf import csrf_exempt
from accounts.models import CustomUser
import logging
import json
from .models import EventoUserResult
from django.contrib.auth.decorators import login_required



logger = logging.getLogger('eventos')


# View to list events
@login_required
def listar_eventos(request):
    eventos = Evento.objects.all()
    return render(request, 'eventos/listar_eventos.html', {'eventos': eventos})

# View to display event details with rounds and matches
@login_required
def detalle_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    rondas = evento.rondas.all()
    return render(request, 'eventos/detalle_evento.html', {'evento': evento, 'rondas': rondas})

# Function to create a new event with dynamic rounds and matches
@login_required
def crear_evento(request):
    if request.method == "POST":
        print(f"Received POST data: {request.POST}")

        # Create the main Evento object
        evento = Evento.objects.create(
            nombre=request.POST['nombre'],
            fecha=request.POST['fecha'],
            ubicacion=request.POST['ubicacion']
        )
        print(f"Evento created: {evento.nombre}")

        # Parse rounds and matches
        rounds_data = {}
        for key, value in request.POST.items():
            if key.startswith("equipo1-round-") or key.startswith("equipo2-round-"):
                try:
                    # Key structure: equipo1-round-{round_number}-match-{match_number}
                    parts = key.split('-')
                    round_number = int(parts[2])  # Extract the round number
                    match_number = int(parts[4])  # Extract the match number

                    if round_number not in rounds_data:
                        rounds_data[round_number] = {}

                    if match_number not in rounds_data[round_number]:
                        rounds_data[round_number][match_number] = {}

                    if key.startswith("equipo1-"):
                        rounds_data[round_number][match_number]['equipo1'] = value
                    elif key.startswith("equipo2-"):
                        rounds_data[round_number][match_number]['equipo2'] = value
                except ValueError as e:
                    print(f"Error parsing key '{key}': {e}")
                    continue

        print(f"Parsed rounds data: {rounds_data}")

        # Save rounds and matches
        for round_number, matches in rounds_data.items():
            ronda = Ronda.objects.create(evento=evento, numero=round_number)
            print(f"Ronda created: {ronda.numero}")
            for match_number, teams in matches.items():
                Pelea.objects.create(
                    ronda=ronda,
                    equipo1=teams['equipo1'],
                    equipo2=teams['equipo2']
                )
                print(f"Pelea created: {teams['equipo1']} vs {teams['equipo2']}")

        return redirect('listar_eventos')

    return render(request, 'eventos/crear_evento.html')
# Function to add a new round to an existing event
def add_round(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    if request.method == "POST":
        numero = request.POST.get("numero")
        if numero:
            Ronda.objects.create(evento=evento, numero=numero)
        return redirect("detalle_evento", evento_id=evento_id)
    return render(request, "eventos/add_round.html", {"evento": evento})

# Function to add a new match to an existing round
def add_match(request, ronda_id):
    ronda = get_object_or_404(Ronda, id=ronda_id)
    if request.method == "POST":
        equipo1 = request.POST.get("equipo1")
        equipo2 = request.POST.get("equipo2")
        if equipo1 and equipo2:
            Pelea.objects.create(ronda=ronda, equipo1=equipo1, equipo2=equipo2)
        return redirect("detalle_evento", evento_id=ronda.evento.id)
    return render(request, "eventos/add_match.html", {"ronda": ronda})

def update_result(request, pelea_id):
    pelea = get_object_or_404(Pelea, id=pelea_id)
    if request.method == "POST":
        resultado = request.POST.get("resultado")
        if resultado in ['equipo1', 'equipo2', 'tie']:
            pelea.resultado = resultado
            pelea.save()

            # Recalculate points for predictions of this fight
            predictions = Prediccion.objects.filter(pelea=pelea)
            for pred in predictions:
                if pred.prediccion == resultado:
                    pred.user.profile.total_points += 1
                    pred.user.profile.save()

            return redirect("detalle_evento", evento_id=pelea.ronda.evento.id)
    return render(request, "eventos/update_result.html", {"pelea": pelea})

def toggle_event_status(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    evento.current = not evento.current  # Toggle current status
    evento.save()
    return redirect('listar_eventos')


def get_current_event(request):
    try:
        current_event = Evento.objects.get(current=True)
        rondas = [
            {
                'id': ronda.id,
                'numero': ronda.numero,
                'peleas': [
                    {
                        'id': pelea.id,
                        'equipo1': pelea.equipo1,
                        'equipo2': pelea.equipo2,
                        'resultado': pelea.resultado
                    } for pelea in ronda.peleas.all()
                ]
            } for ronda in current_event.rondas.all()
        ]
        response = {
            'id': current_event.id,
            'nombre': current_event.nombre,
            'fecha': current_event.fecha,
            'ubicacion': current_event.ubicacion,
            'rondas': rondas
        }
        return JsonResponse(response, safe=False)
    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No hay un evento activo.'}, status=404)

@csrf_exempt
def submit_predictions(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            predictions = data.get('predictions', {})

            user = CustomUser.objects.get(user_id=user_id)
            current_event = Evento.objects.get(current=True)

            total_points = 0

            for pelea_id, prediccion in predictions.items():
                pelea = Pelea.objects.get(id=pelea_id)

                # Store the prediction
                user_prediction, created = Prediccion.objects.update_or_create(
                    user=user,
                    pelea=pelea,
                    defaults={'prediccion': prediccion}
                )

                # Update points if the fight result is already known
                if pelea.resultado and pelea.resultado == prediccion:
                    total_points += 1

            # Update points in the EventoUserResult model
            EventoUserResult.objects.update_or_create(
                user=user,
                evento=current_event,
                defaults={'total_points': total_points}
            )

            return JsonResponse({'message': 'Predictions submitted successfully.', 'total_points': total_points})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def check_participation(request):
    if request.method == 'GET':
        try:
            user_id = request.GET.get('user_id')
            event_id = request.GET.get('event_id')

            user = CustomUser.objects.get(user_id=user_id)
            evento = Evento.objects.get(id=event_id)

            participated = EventoUserResult.objects.filter(user=user, evento=evento).exists()

            return JsonResponse({
                'participated': participated
            }, status=200)

        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'User not found.'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Event not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid method.'}, status=405)

@csrf_exempt
def use_ticket(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            event_id = data.get('event_id')

            user = CustomUser.objects.get(user_id=user_id)
            evento = Evento.objects.get(id=event_id)

            # Check participation again for safety
            if EventoUserResult.objects.filter(user=user, evento=evento).exists():
                return JsonResponse({
                    'error': 'Ya has participado en este evento'
                }, status=400)

            # Check ticket availability
            if user.event_tickets <= 0:
                return JsonResponse({'error': 'Not enough tickets to participate.'}, status=400)

            # Deduct ticket and grant access
            user.event_tickets -= 1
            user.save()

            # Register user for the event
            EventoUserResult.objects.create(user=user, evento=evento, total_points=0)

            return JsonResponse({'message': 'Participation granted. Ticket used successfully.'}, status=200)

        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'User not found.'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Event not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid method.'}, status=405)

@csrf_exempt
def get_user_results(request):
    try:
        user_id = request.GET.get('user_id')
        user = CustomUser.objects.get(user_id=user_id)
        current_event = Evento.objects.get(current=True)

        prediction_results = []
        total_points = 0

        if current_event.results_visible:
            predictions = Prediccion.objects.filter(user=user, pelea__ronda__evento=current_event)
            for pred in predictions:
                prediction_results.append({
                    'pelea_id': pred.pelea.id,
                    'equipo1': pred.pelea.equipo1,
                    'equipo2': pred.pelea.equipo2,
                    'prediccion': pred.prediccion,
                    'resultado': pred.pelea.resultado,
                    'correct': pred.prediccion == pred.pelea.resultado,
                })
                if pred.prediccion == pred.pelea.resultado:
                    total_points += 1

        return JsonResponse({
            'resultsVisible': current_event.results_visible,
            'predictionResults': prediction_results,
            'totalPoints': total_points
        }, status=200)

    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)
    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No active event.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def toggle_results_visibility(request, evento_id):
    if request.method == 'POST':
        try:
            evento = Evento.objects.get(id=evento_id)
            evento.results_visible = not evento.results_visible
            evento.save()

            return redirect('listar_eventos')  # Redirect back to the events list

        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Event not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid method.'}, status=405)

@csrf_exempt
def get_rankings(request, evento_id):
    try:
        evento = Evento.objects.get(id=evento_id)

        if not evento.ranking_visible:
            return JsonResponse({'error': 'Ranking is currently hidden.'}, status=403)

        results = EventoUserResult.objects.filter(evento=evento).order_by('-total_points')[:10]
        rankings = [
            {'user': result.user.user_id, 'points': result.total_points}
            for result in results
        ]

        return JsonResponse({'rankings': rankings}, status=200)

    except Evento.DoesNotExist:
        return JsonResponse({'error': 'Event not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def toggle_ranking_visibility(request, evento_id):
    if request.method == 'POST':
        try:
            evento = Evento.objects.get(id=evento_id)
            evento.ranking_visible = not evento.ranking_visible
            evento.save()

            return JsonResponse({
                'message': 'Ranking visibility toggled successfully.',
                'ranking_visible': evento.ranking_visible
            }, status=200)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Event not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid method.'}, status=405)