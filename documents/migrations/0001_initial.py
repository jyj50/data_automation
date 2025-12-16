from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255)),
                ("file", models.FileField(upload_to="documents/")),
                ("checksum", models.CharField(db_index=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("scanned_or_empty", "Scanned or Empty"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=32,
                    ),
                ),
                ("num_pages", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DocumentPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("page_number", models.PositiveIntegerField()),
                ("text_raw", models.TextField(blank=True)),
                ("text_clean", models.TextField(blank=True)),
                (
                    "document",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="pages", to="documents.document"),
                ),
            ],
            options={
                "ordering": ["page_number"],
                "unique_together": {("document", "page_number")},
            },
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("page_start", models.PositiveIntegerField()),
                ("page_end", models.PositiveIntegerField()),
                ("text", models.TextField()),
                ("token_count", models.PositiveIntegerField(blank=True, null=True)),
                ("embedding_id", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="chunks", to="documents.document"),
                ),
            ],
            options={
                "ordering": ["chunk_index"],
                "unique_together": {("document", "chunk_index")},
            },
        ),
    ]
