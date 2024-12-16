from django.urls import path
from . import views

urlpatterns = [
    path('', views.listar_eventos, name='listar_eventos'),
    path('eventos/<int:evento_id>/', views.detalle_evento, name='detalle_evento'),
    path('eventos/crear/', views.crear_evento, name='crear_evento'),
    path('<int:evento_id>/add-round/', views.add_round, name='add_round'),
    path('ronda/<int:ronda_id>/add-match/', views.add_match, name='add_match'),
    path("pelea/<int:pelea_id>/update/", views.update_result, name="update_result"),
    path('api/current-event/', views.get_current_event, name='get_current_event'),
    path('toggle/<int:evento_id>/', views.toggle_event_status, name='toggle_event_status'),
    path('api/submit-predictions/', views.submit_predictions, name='submit_predictions'),
    path('api/check-participation/', views.check_participation, name='check_participation'),
    path('api/user-results/', views.get_user_results, name='get_user_results'),
    path('eventos/<int:evento_id>/toggle-results/', views.toggle_results_visibility, name='toggle_results'),
    path('api/rankings/<int:evento_id>/', views.get_rankings, name='get_rankings'),
    path('api/toggle-ranking/<int:evento_id>/', views.toggle_ranking_visibility, name='toggle_ranking_visibility'),

]
