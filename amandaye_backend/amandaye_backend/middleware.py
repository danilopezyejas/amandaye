from django.shortcuts import redirect


class Redirect404Middleware:
    """
    Middleware que intercepta respuestas 404 y redirige al usuario
    de vuelta a la última URL conocida o a una URL base sensata.
    Funciona independientemente del valor de DEBUG.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 404:
            referer = request.META.get('HTTP_REFERER', '')
            req_path = request.path

            if referer:
                return redirect(referer)

            if req_path.startswith('/admin/'):
                return redirect('/admin/')

            return redirect('/login/')

        return response
