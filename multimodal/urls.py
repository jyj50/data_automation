from django.urls import path
from . import views

app_name = 'multimodal'

urlpatterns = [
    # 메인 페이지
    path('', views.home, name='home'),

    # 이미지 처리 관련 URL
    path('image/', views.image_tab, name='image_tab'),
    path('image/upload/', views.image_upload, name='image_upload'),
    path('image/segment/', views.image_segment, name='image_segment'),
    path('image/<int:image_id>/', views.image_detail, name='image_detail'),

    # 텍스트 처리 관련 URL
    path('text/', views.text_tab, name='text_tab'),
    path('text/process/', views.text_process, name='text_process'),
    path('text/upload/', views.text_upload, name='text_upload'),

    # 음성 처리 관련 URL
    path('audio/', views.audio_tab, name='audio_tab'),
    path('audio/upload/', views.audio_upload, name='audio_upload'),
    path('audio/<int:audio_id>/', views.audio_detail, name='audio_detail'),
]