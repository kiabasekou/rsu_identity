
from django.http import JsonResponse

def survey_list(request):
    return JsonResponse({'message': 'Surveys app is working', 'status': 'success'})
