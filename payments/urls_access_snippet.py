# Add this import to payments/urls.py:
from .access_views import ChapterAccessCheckView

# Add this path to urlpatterns:
path(
    "access/chapters/<int:chapter_id>/",
    ChapterAccessCheckView.as_view(),
    name="chapter-access-check",
),
