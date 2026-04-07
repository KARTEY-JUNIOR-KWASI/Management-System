from django.db import models


class Resource(models.Model):
    """
    A learning resource uploaded by a teacher.
    Students can browse and download resources from the Library portal.
    """

    RESOURCE_TYPES = [
        ('document', 'Document (PDF, Word, etc.)'),
        ('video', 'Video'),
        ('presentation', 'Presentation (PPT)'),
        ('spreadsheet', 'Spreadsheet'),
        ('image', 'Image'),
        ('link', 'External Link'),
        ('other', 'Other'),
    ]

    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='document')

    # File OR link (one must be provided)
    file         = models.FileField(upload_to='library/resources/', null=True, blank=True)
    external_url = models.URLField(blank=True, help_text="For external links / YouTube videos")

    # Metadata
    subject    = models.ForeignKey('core.Subject', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='library_uploads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)

    # Access control
    target_class = models.ForeignKey(
        'core.Class', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Leave blank to share with all students"
    )
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def icon(self):
        icons = {
            'document': 'fa-file-pdf',
            'video': 'fa-film',
            'presentation': 'fa-file-powerpoint',
            'spreadsheet': 'fa-file-excel',
            'image': 'fa-image',
            'link': 'fa-link',
            'other': 'fa-file',
        }
        return icons.get(self.resource_type, 'fa-file')

    @property
    def color(self):
        colors = {
            'document': '#e74c3c',
            'video': '#9b59b6',
            'presentation': '#e67e22',
            'spreadsheet': '#27ae60',
            'image': '#3498db',
            'link': '#1abc9c',
            'other': '#95a5a6',
        }
        return colors.get(self.resource_type, '#95a5a6')
