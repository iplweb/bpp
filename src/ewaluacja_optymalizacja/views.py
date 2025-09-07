from django.shortcuts import render

from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    """
    Główny widok aplikacji ewaluacja_optymalizacja - strona "Coming Soon"
    """
    return render(request, "ewaluacja_optymalizacja/index.html")
