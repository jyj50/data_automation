from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.home, name="home"),  # HTML landing/upload page (wizard)
    path("documents/<int:document_id>/", views.document_detail_page, name="detail_page"),
    path("manage/documents/", views.manage_documents, name="manage_documents"),
    path("manage/documents/<int:document_id>/", views.manage_document_detail, name="manage_document_detail"),
    path("chat/", views.chat_page, name="chat_page"),
    # JSON API
    path("api/", views.index, name="api_index"),
    path("api/documents/upload/", views.upload_document, name="upload"),
    path("api/documents/<int:document_id>/", views.document_detail, name="detail"),
    path("api/documents/<int:document_id>/pages/", views.document_pages, name="pages"),
    path(
        "api/documents/<int:document_id>/pages/<int:page_no>/preview/",
        views.document_page_preview,
        name="page_preview",
    ),
    path("api/documents/<int:document_id>/parse/", views.parse_document_view, name="parse"),
    path("api/articles/<int:article_id>/", views.update_article, name="update_article"),
    path("api/documents/<int:document_id>/upsert/", views.upsert_view, name="upsert"),
    path(
        "api/documents/<int:document_id>/generate-questions/",
        views.generate_questions_view,
        name="generate_questions",
    ),
    path("api/chat/", views.chat_api, name="chat_api"),
]
