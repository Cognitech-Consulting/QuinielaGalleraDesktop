from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from .models import Evento, Ronda, Pelea, Prediccion, NombreEquipo
from .forms import EventoForm, NombreEquipoForm
from django.views.decorators.csrf import csrf_exempt
from accounts.models import CustomUser
import logging
import json
from .models import EventoUserResult
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('eventos')


# View to list events
@login_required
def listar_eventos(request):
    search_query = request.GET.get('search', '')  # Get the search query from the request
    eventos = Evento.objects.all().order_by('-fecha')  # Order by most recent first

    if search_query:
        # Filter events by nombre or fecha (case-insensitive)
        eventos = eventos.filter(
            Q(nombre__icontains=search_query) |
            Q(fecha__icontains=search_query)
        )

    return render(request, 'eventos/listar_eventos.html', {
        'eventos': eventos,
        'search': search_query
    })


# View to display event details with rounds and matches
@login_required
def detalle_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    rondas = evento.rondas.all().order_by('numero')
    return render(request, 'eventos/detalle_evento.html', {'evento': evento, 'rondas': rondas})


@login_required
def crear_evento(request):
    """
    UNIFIED event creation view - handles event, teams, and fights in ONE request.
    NO redirects, NO separate pages, everything on one page!
    """
    if request.method == 'POST':
        try:
            # Get event basic info
            nombre = request.POST.get('nombre')
            fecha_evento = request.POST.get('fecha_evento')
            ubicacion = request.POST.get('ubicacion')

            # Get JSON data for teams and fights
            teams_data = json.loads(request.POST.get('teams_data', '[]'))
            fights_data = json.loads(request.POST.get('fights_data', '[]'))

            # Validate
            if not nombre or not fecha_evento or not ubicacion:
                messages.error(request, '❌ Completa todos los campos del evento')
                return render(request, 'eventos/crear_evento.html')

            if len(teams_data) < 2:
                messages.error(request, '❌ Debes registrar al menos 2 equipos')
                return render(request, 'eventos/crear_evento.html')

            if len(fights_data) == 0:
                messages.error(request, '❌ Debes crear al menos 1 pelea')
                return render(request, 'eventos/crear_evento.html')

            # Create everything in ONE atomic transaction
            with transaction.atomic():
                # 1. Create Event
                evento = Evento.objects.create(
                    nombre=nombre,
                    fecha=fecha_evento,
                    ubicacion=ubicacion
                )

                # 2. Create Teams
                team_map = {}  # Map team numbers to team names
                for team_data in teams_data:
                    NombreEquipo.objects.create(
                        evento=evento,
                        nombre=team_data['name'],
                        valor=int(team_data['number'])
                    )
                    team_map[team_data['number']] = team_data['name']

                # 3. Create ONE default round
                ronda = Ronda.objects.create(
                    evento=evento,
                    numero=1
                )

                # 4. Create Fights
                for fight_data in fights_data:
                    team1_number = fight_data['team1']
                    team2_number = fight_data['team2']

                    # Get team names from map
                    equipo1_nombre = team_map.get(team1_number)
                    equipo2_nombre = team_map.get(team2_number)

                    if not equipo1_nombre or not equipo2_nombre:
                        raise ValueError(f"Invalid team numbers in fight {fight_data['numero_pelea']}")

                    # Create fight
                    Pelea.objects.create(
                        ronda=ronda,
                        equipo1=equipo1_nombre,
                        equipo2=equipo2_nombre
                    )

                # Success!
                messages.success(request, f'✅ Evento "{nombre}" creado exitosamente con {len(teams_data)} equipos y {len(fights_data)} peleas!')
                return redirect('detalle_evento', evento_id=evento.id)

        except json.JSONDecodeError:
            messages.error(request, '❌ Error al procesar los datos. Intenta nuevamente.')
            return render(request, 'eventos/crear_evento.html')
        except ValueError as e:
            messages.error(request, f'❌ Error: {str(e)}')
            return render(request, 'eventos/crear_evento.html')
        except Exception as e:
            messages.error(request, f'❌ Error inesperado: {str(e)}')
            return render(request, 'eventos/crear_evento.html')

    # GET request - show the form
    return render(request, 'eventos/crear_evento.html')


@login_required
def crear_rondas(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    if request.method == "POST":
        rounds_data = {}

        for key, value in request.POST.items():
            if key.startswith("equipo1-round-") or key.startswith("equipo2-round-"):
                try:
                    parts = key.split('-')
                    round_number = int(parts[2])
                    match_number = int(parts[4])

                    if round_number not in rounds_data:
                        rounds_data[round_number] = {}
                    if match_number not in rounds_data[round_number]:
                        rounds_data[round_number][match_number] = {}

                    # Parse valor (handle "valor:nombre" format)
                    valor_str = value.split(':')[0].strip()
                    valor_int = int(valor_str)

                    # Get the team name from NombreEquipo
                    try:
                        equipo = NombreEquipo.objects.get(evento_id=evento_id, valor=valor_int)
                        nombre_equipo = equipo.nombre
                    except NombreEquipo.DoesNotExist:
                        messages.error(request, f'Equipo con valor {valor_int} no encontrado')
                        continue

                    if key.startswith("equipo1-"):
                        rounds_data[round_number][match_number]['equipo1'] = nombre_equipo
                    elif key.startswith("equipo2-"):
                        rounds_data[round_number][match_number]['equipo2'] = nombre_equipo

                except Exception as e:
                    logger.error(f"Error processing match key={key}: {e}")
                    continue

        # Create rounds and fights
        if rounds_data:
            for round_number, matches in rounds_data.items():
                ronda, created = Ronda.objects.get_or_create(evento=evento, numero=round_number)
                for match_number, teams in matches.items():
                    if 'equipo1' in teams and 'equipo2' in teams:
                        Pelea.objects.create(
                            ronda=ronda,
                            equipo1=teams['equipo1'],
                            equipo2=teams['equipo2']
                        )

            messages.success(request, 'Rondas y peleas creadas exitosamente!')
            return redirect('detalle_evento', evento_id=evento.id)
        else:
            messages.warning(request, 'No se encontraron peleas para crear')

    return render(request, 'eventos/crear_ronda.html', {
        'evento': evento,
        'equipos_url': reverse('gestionar_equipos', args=[evento.id])
    })


# FUNCIÓN MEJORADA: Add a new round to an existing event WITH MULTIPLE FIGHTS
@login_required
def add_round(request, evento_id):
    """
    Add a new round to an existing event with multiple fights
    """
    evento = get_object_or_404(Evento, id=evento_id)
    equipos = NombreEquipo.objects.filter(evento=evento).order_by('valor')
    
    # Calculate next round number
    existing_rounds = Ronda.objects.filter(evento=evento)
    next_round_number = existing_rounds.count() + 1 if existing_rounds.exists() else 1
    
    if request.method == 'POST':
        try:
            # Get round number
            round_number = int(request.POST.get('round_number', next_round_number))
            
            # Get fights data
            fights_data = json.loads(request.POST.get('fights_data', '[]'))
            
            # Validate
            if len(fights_data) == 0:
                messages.error(request, '❌ Debes crear al menos 1 pelea')
                return render(request, 'eventos/crear_ronda.html', {
                    'evento': evento,
                    'equipos': equipos,
                    'next_round_number': next_round_number
                })
            
            # Create team number to name mapping
            team_map = {str(equipo.valor): equipo.nombre for equipo in equipos}
            
            # Create everything in one transaction
            with transaction.atomic():
                # Check if round number already exists
                if Ronda.objects.filter(evento=evento, numero=round_number).exists():
                    messages.error(request, f'❌ La ronda {round_number} ya existe')
                    return render(request, 'eventos/crear_ronda.html', {
                        'evento': evento,
                        'equipos': equipos,
                        'next_round_number': next_round_number
                    })
                
                # Create the round
                ronda = Ronda.objects.create(
                    evento=evento,
                    numero=round_number
                )
                
                # Create all fights for this round
                for fight_data in fights_data:
                    team1_number = fight_data['team1']
                    team2_number = fight_data['team2']
                    
                    # Get team names
                    equipo1_nombre = team_map.get(team1_number)
                    equipo2_nombre = team_map.get(team2_number)
                    
                    if not equipo1_nombre or not equipo2_nombre:
                        raise ValueError(f"Invalid team numbers in fight {fight_data['numero_pelea']}")
                    
                    # Create fight
                    Pelea.objects.create(
                        ronda=ronda,
                        equipo1=equipo1_nombre,
                        equipo2=equipo2_nombre
                    )
                
                messages.success(request, f'✅ Ronda {round_number} creada con {len(fights_data)} peleas!')
                return redirect('detalle_evento', evento_id=evento.id)
                
        except json.JSONDecodeError:
            messages.error(request, '❌ Error al procesar los datos')
        except ValueError as e:
            messages.error(request, f'❌ Error: {str(e)}')
        except Exception as e:
            logger.error(f"Error adding round: {str(e)}")
            messages.error(request, f'❌ Error inesperado: {str(e)}')
    
    # GET request - show the form
    return render(request, 'eventos/crear_ronda.html', {
        'evento': evento,
        'equipos': equipos,
        'next_round_number': next_round_number
    })


# FUNCIÓN MEJORADA: Add a single fight to an existing round
@login_required
def add_match(request, ronda_id):
    """
    Add a single fight to an existing round
    """
    ronda = get_object_or_404(Ronda, id=ronda_id)
    equipos = NombreEquipo.objects.filter(evento=ronda.evento).order_by('valor')
    
    if request.method == "POST":
        equipo1 = request.POST.get("equipo1")
        equipo2 = request.POST.get("equipo2")
        
        if equipo1 and equipo2:
            Pelea.objects.create(ronda=ronda, equipo1=equipo1, equipo2=equipo2)
            messages.success(request, f'✅ Pelea añadida: {equipo1} vs {equipo2}')
            return redirect("detalle_evento", evento_id=ronda.evento.id)
        else:
            messages.error(request, '❌ Selecciona ambos equipos')
    
    return render(request, "eventos/agregar_pelea.html", {
        "ronda": ronda,
        "equipos": equipos
    })


@login_required
def update_result(request, pelea_id):
    """
    FIXED VERSION: Properly updates fight results and recalculates points
    without accessing non-existent user.profile
    """
    pelea = get_object_or_404(Pelea, id=pelea_id)

    if request.method == "POST":
        resultado = request.POST.get("resultado")

        if resultado in ['equipo1', 'equipo2', 'tie']:
            with transaction.atomic():
                # Save the result
                pelea.resultado = resultado
                pelea.save()

                # Get the event
                evento = pelea.ronda.evento

                # Get all predictions for this fight
                predictions = Prediccion.objects.filter(pelea=pelea)

                # Get unique users who made predictions for this fight
                users_to_update = set(pred.user for pred in predictions)

                # For each user, recalculate their TOTAL points for this event
                for user in users_to_update:
                    # Get all predictions by this user for this event
                    user_predictions = Prediccion.objects.filter(
                        user=user,
                        pelea__ronda__evento=evento
                    )

                    # Calculate total correct predictions
                    total_points = sum(
                        1 for pred in user_predictions
                        if pred.pelea.resultado and pred.prediccion == pred.pelea.resultado
                    )

                    # Update or create the EventoUserResult
                    EventoUserResult.objects.update_or_create(
                        user=user,
                        evento=evento,
                        defaults={'total_points': total_points}
                    )

                messages.success(request, f'Resultado actualizado: {resultado}')

            return redirect("detalle_evento", evento_id=pelea.ronda.evento.id)
        else:
            messages.error(request, 'Resultado inválido')

    return render(request, "eventos/update_result.html", {"pelea": pelea})


@csrf_exempt
def submit_predictions(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            event_id = data.get('event_id')
            predictions_data = data.get('predictions', [])

            if not all([user_id, event_id, predictions_data]):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)

            user = CustomUser.objects.get(user_id=user_id)
            evento = Evento.objects.get(id=event_id)

            # Check if user already participated
            if EventoUserResult.objects.filter(user=user, evento=evento).exists():
                return JsonResponse({'error': 'Ya has participado en este evento'}, status=400)

            # Check if user has tickets
            if user.event_tickets < 1:
                return JsonResponse({'error': 'No tienes boletos disponibles'}, status=400)

            with transaction.atomic():
                # Deduct one ticket
                user.event_tickets -= 1
                user.save()

                # Create predictions
                for pred_data in predictions_data:
                    pelea_id = pred_data.get('pelea_id')
                    prediccion = pred_data.get('prediccion')

                    pelea = Pelea.objects.get(id=pelea_id)
                    Prediccion.objects.update_or_create(
                        user=user,
                        pelea=pelea,
                        defaults={'prediccion': prediccion}
                    )

                # Create EventoUserResult entry
                EventoUserResult.objects.create(
                    user=user,
                    evento=evento,
                    total_points=0
                )

            return JsonResponse({
                'success': True,
                'message': 'Predicciones guardadas exitosamente',
                'tickets_remaining': user.event_tickets
            }, status=200)

        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Evento no encontrado'}, status=404)
        except Pelea.DoesNotExist:
            return JsonResponse({'error': 'Pelea no encontrada'}, status=404)
        except Exception as e:
            logger.error(f"Error submitting predictions: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método inválido'}, status=405)


@csrf_exempt
def get_user_predictions(request):
    if request.method == 'GET':
        try:
            user_id = request.GET.get('user_id')
            event_id = request.GET.get('event_id')

            if not user_id or not event_id:
                return JsonResponse({'error': 'Faltan parámetros'}, status=400)

            user = CustomUser.objects.get(user_id=user_id)
            evento = Evento.objects.get(id=event_id)

            participated = EventoUserResult.objects.filter(user=user, evento=evento).exists()

            return JsonResponse({
                'participated': participated,
                'tickets_available': user.event_tickets
            }, status=200)

        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Evento no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método inválido'}, status=405)


@csrf_exempt
def get_user_results(request):
    try:
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return JsonResponse({'error': 'Falta user_id'}, status=400)
            
        user = CustomUser.objects.get(user_id=user_id)
        current_event = Evento.objects.get(current=True)

        prediction_results = []
        total_points = 0

        if current_event.results_visible:
            predictions = Prediccion.objects.filter(
                user=user, 
                pelea__ronda__evento=current_event
            ).select_related('pelea')
            
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
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No hay evento activo'}, status=404)
    except Exception as e:
        logger.error(f"Error getting user results: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def toggle_results_visibility(request, evento_id):
    if request.method in ['GET', 'POST']:
        try:
            evento = Evento.objects.get(id=evento_id)
            evento.results_visible = not evento.results_visible
            evento.save()

            status = "visibles" if evento.results_visible else "ocultos"
            messages.success(request, f'Resultados {status} para "{evento.nombre}"')
            return redirect('listar_eventos')

        except Evento.DoesNotExist:
            messages.error(request, 'Evento no encontrado')
            return redirect('listar_eventos')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('listar_eventos')

    return JsonResponse({'error': 'Método inválido'}, status=405)


@csrf_exempt
def get_rankings(request, evento_id):
    try:
        evento = Evento.objects.get(id=evento_id)

        if not evento.ranking_visible:
            return JsonResponse({'error': 'Ranking actualmente oculto'}, status=403)

        results = EventoUserResult.objects.filter(evento=evento).order_by('-total_points')[:10]
        rankings = [
            {
                'user': result.user.user_id,
                'nombre': f"{result.user.nombre or ''} {result.user.apellido or ''}".strip() or result.user.user_id,
                'points': result.total_points
            }
            for result in results
        ]

        return JsonResponse({'rankings': rankings}, status=200)

    except Evento.DoesNotExist:
        return JsonResponse({'error': 'Evento no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error getting rankings: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def toggle_ranking_visibility(request, evento_id):
    if request.method in ['GET', 'POST']:
        try:
            evento = Evento.objects.get(id=evento_id)
            evento.ranking_visible = not evento.ranking_visible
            evento.save()

            return JsonResponse({
                'message': 'Visibilidad del ranking actualizada',
                'ranking_visible': evento.ranking_visible
            }, status=200)
        except Evento.DoesNotExist:
            return JsonResponse({'error': 'Evento no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método inválido'}, status=405)


@login_required
def gestionar_equipos(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    equipos = NombreEquipo.objects.filter(evento=evento).order_by('valor')

    if request.method == 'POST':
        form = NombreEquipoForm(request.POST)
        if form.is_valid():
            nuevo_equipo = form.save(commit=False)
            nuevo_equipo.evento = evento
            try:
                nuevo_equipo.save()
                messages.success(request, f'Equipo #{nuevo_equipo.valor} "{nuevo_equipo.nombre}" añadido')
                return redirect('gestionar_equipos', evento_id=evento.id)
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario')
    else:
        form = NombreEquipoForm()

    return render(request, 'eventos/gestionar_equipos.html', {
        'evento': evento,
        'equipos': equipos,
        'form': form,
    })


def obtener_nombre_equipo(request, evento_id):
    """Get team name by valor for a specific event"""
    valor = request.GET.get('valor')

    if not valor:
        return JsonResponse({'error': 'Falta valor'}, status=400)

    try:
        valor_int = int(valor)
        equipo = NombreEquipo.objects.get(evento_id=evento_id, valor=valor_int)
        return JsonResponse({'nombre': equipo.nombre}, status=200)
    except ValueError:
        return JsonResponse({'error': 'Valor debe ser numérico'}, status=400)
    except NombreEquipo.DoesNotExist:
        return JsonResponse({'error': 'Equipo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def buscar_equipo_global(request):
    """Search for team globally (for mobile app)"""
    valor = request.GET.get('valor')

    if not valor:
        return JsonResponse({'error': 'Falta valor'}, status=400)

    try:
        valor_int = int(valor)
        # Get the current event's team
        current_event = Evento.objects.get(current=True)
        equipo = NombreEquipo.objects.get(evento=current_event, valor=valor_int)
        return JsonResponse({'nombre': equipo.nombre}, status=200)
    except ValueError:
        return JsonResponse({'error': 'Valor debe ser numérico'}, status=400)
    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No hay evento activo'}, status=404)
    except NombreEquipo.DoesNotExist:
        return JsonResponse({'error': 'Equipo no encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Error in buscar_equipo_global: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_current_event(request):
    """Get the currently active event with all its rounds and fights"""
    try:
        current_event = Evento.objects.get(current=True)

        # Get all rounds for this event
        rondas = Ronda.objects.filter(evento=current_event).order_by('numero')

        rounds_data = []
        for ronda in rondas:
            peleas = Pelea.objects.filter(ronda=ronda)
            fights_data = [
                {
                    'id': pelea.id,
                    'equipo1': pelea.equipo1,
                    'equipo2': pelea.equipo2,
                    'resultado': pelea.resultado if pelea.resultado else None
                }
                for pelea in peleas
            ]

            rounds_data.append({
                'id': ronda.id,
                'numero': ronda.numero,
                'peleas': fights_data
            })

        return JsonResponse({
            'id': current_event.id,
            'nombre': current_event.nombre,
            'fecha': str(current_event.fecha),
            'ubicacion': current_event.ubicacion,
            'rondas': rounds_data,
            'results_visible': current_event.results_visible,
            'ranking_visible': current_event.ranking_visible
        }, status=200)

    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No hay evento activo'}, status=404)
    except Exception as e:
        logger.error(f"Error getting current event: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def check_participation(request):
    """Check if a user has already participated in the current event"""
    try:
        user_id = request.GET.get('user_id')

        if not user_id:
            return JsonResponse({'error': 'Falta user_id'}, status=400)

        user = CustomUser.objects.get(user_id=user_id)
        current_event = Evento.objects.get(current=True)

        # Check if user has already submitted predictions for this event
        has_participated = EventoUserResult.objects.filter(
            user=user,
            evento=current_event
        ).exists()

        return JsonResponse({
            'has_participated': has_participated,
            'event_id': current_event.id,
            'event_name': current_event.nombre,
            'tickets_available': user.event_tickets
        }, status=200)

    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    except Evento.DoesNotExist:
        return JsonResponse({'error': 'No hay evento activo'}, status=404)
    except Exception as e:
        logger.error(f"Error checking participation: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def toggle_event_status(request, evento_id):
    """Toggle the current status of an event (activate/deactivate)"""
    if request.method == 'POST':
        try:
            evento = Evento.objects.get(id=evento_id)

            if evento.current:
                # Deactivate this event
                evento.current = False
                evento.save()
                messages.success(request, f'Evento "{evento.nombre}" desactivado')
            else:
                # Activate this event (and deactivate all others)
                Evento.objects.filter(current=True).update(current=False)
                evento.current = True
                evento.save()
                messages.success(request, f'Evento "{evento.nombre}" activado')

            return redirect('listar_eventos')

        except Evento.DoesNotExist:
            messages.error(request, 'Evento no encontrado')
            return redirect('listar_eventos')
        except Exception as e:
            logger.error(f"Error toggling event status: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
            return redirect('listar_eventos')

    return JsonResponse({'error': 'Método inválido'}, status=405)