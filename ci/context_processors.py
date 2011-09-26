from django.contrib.sites.models import Site

def site(request):
    return {'current_site': Site.objects.get_current()}
