from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="document",
            old_name="num_pages",
            new_name="page_count",
        ),
        migrations.AddField(
            model_name="document",
            name="parse_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="not_started",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="question_gen_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="not_started",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="selected_page_end",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="selected_page_start",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="upsert_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="not_started",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="documentpage",
            name="preview_image_path",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_key", models.CharField(db_index=True, max_length=50)),
                ("title_in_parens", models.CharField(blank=True, max_length=255)),
                ("full_title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("chapter_title", models.CharField(blank=True, max_length=255)),
                ("section_title", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                ("source_pages", models.JSONField(blank=True, default=list)),
                ("user_edited", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="articles", to="documents.document"
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
                "unique_together": {("document", "article_key")},
            },
        ),
        migrations.CreateModel(
            name="GeneratedQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_text", models.TextField()),
                ("expected_answer_snippet", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "article",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="questions",
                        to="documents.article",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="questions", to="documents.document"
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ArticleChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("chunk_text", models.TextField()),
                ("embedding_id", models.CharField(blank=True, max_length=255)),
                ("vector_id", models.CharField(blank=True, max_length=255)),
                ("token_count", models.PositiveIntegerField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="chunks", to="documents.article"
                    ),
                ),
            ],
            options={
                "ordering": ["chunk_index"],
                "unique_together": {("article", "chunk_index")},
            },
        ),
    ]
