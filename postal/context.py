from django.conf import settings


def site(request):
    """Values every page needs: the hosted demo's end date and where to get the code."""
    return {"demo_until": settings.DEMO_UNTIL, "repository_url": settings.REPOSITORY_URL}
