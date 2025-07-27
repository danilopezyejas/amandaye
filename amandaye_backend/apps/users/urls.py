from django.shortcuts import render, get_object_or_404, redirect
from .models import Personas

def buscar_persona(request):
    cedula = request.GET.get('cedula', '').strip()
    personas = Personas.objects.filter(Cedula=cedula)

    if personas.count() == 1:
        return redirect('detalle_persona', pk=personas.first().pk)
    elif personas.exists():
        return render(request, 'users/seleccionar_persona.html', {'personas': personas, 'cedula': cedula})
    else:
        return render(request, 'users/no_encontrado.html', {'cedula': cedula})


def detalle_persona(request, pk):
    persona = get_object_or_404(Personas, pk=pk)
    return render(request, 'users/detalle_persona.html', {'persona': persona})
