import openai

from rest_framework import viewsets
from django.contrib.auth import logout, get_user_model
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from decouple import config

from .filters import UserBasicFilter, UserSearchesFilter
from .models import User, UserSearches
from .serializers import UserSerializer, UserBasicDataSerializer, UserSearchesSerializer
from .services import auth_login, auth_register_user, auth_password_change
from ..base import response
from ..base.serializers import SawaggerResponseSerializer
from ..base.api.pagination import StandardResultsSetPagination


class UserViewSet(viewsets.ModelViewSet):
    """
    Here we have user login, logout, endpoints.
    """
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    filterset_class = None

    def get_queryset(self):
        queryset = super(UserViewSet, self).get_queryset()
        queryset = queryset.filter(is_active=True)
        self.filterset_class = UserBasicFilter
        queryset = self.filter_queryset(queryset)
        return queryset

    @swagger_auto_schema(
        method="post",
        operation_summary='Login',
        operation_description='Post login credential to log in and get a login session token.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description="mobile/email"),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description=""),
            }),
        responses={
            200: SawaggerResponseSerializer(data={'message': 'Logged In'}, partial=True)
        }
    )
    @action(detail=False, methods=['POST'])
    def login(self, request):
        return auth_login(request)

    @action(detail=False, methods=['POST'])
    def logout(self, request):
        if request.user.is_authenticated:
            Token.objects.filter(user=request.user).delete()
            logout(request)
        return response.Ok({"detail": "Successfully logged out."})

    @action(detail=False, methods=['POST'])
    def register(self, request):
        data = auth_register_user(request)
        return response.Created(data)

    @action(methods=['GET'], detail=False, pagination_class=StandardResultsSetPagination)
    def users_list(self, request):
        queryset = User.objects.filter(is_active=True, is_separated=False, is_superuser=False,
                                       is_staff=False)
        queryset = queryset.order_by('first_name', 'last_name')
        self.filterset_class = UserBasicFilter
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(UserBasicDataSerializer(page, many=True).data)
        return response.Ok(UserBasicDataSerializer(queryset, many=True).data)

    @swagger_auto_schema(
        method="post",
        operation_summary='Change Password',
        operation_description='Post old and new password while logged in session.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'old_password': openapi.Schema(type=openapi.TYPE_STRING, description=""),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description=""),
            }),
        responses={
            200: SawaggerResponseSerializer(data={'message': 'Password changed Successfully.'}, partial=True)
        }
    )
    @action(detail=False, methods=['POST'])
    def password_change(self, request):
        data = auth_password_change(request)
        user, new_password = request.user, data.get('new_password')
        if new_password:
            if len(new_password) < 6:
                return response.BadRequest({"detail": "Password too short."})
        if user.check_password(data.get('old_password')):
            user.set_password(new_password)
            user.save()
            content = {'success': 'Password changed successfully.'}
            return response.Ok(content)
        else:
            content = {'detail': 'Old password is incorrect.'}
            return response.BadRequest(content)

    @action(detail=False, methods=['POST'])
    def superadmin_password_reset(self, request):
        data = request.data.copy()
        user_id = data.get('user', None)
        password = data.get('password', None)
        if user_id:
            user = get_user_model().objects.filter(pk=user_id).first()
            if user:
                if password:
                    if len(password) < 8:
                        return response.BadRequest({"detail": "Password Length too short."})
                    user.set_password(password)
                    user.save()
                    content = {'success': 'Password changed successfully.'}
                    return response.Ok(content)
                return response.BadRequest({"detail": "Password is Null."})
            return response.BadRequest({"detail": "User Doesn't exist."})
        return response.BadRequest({"detail": "User is required."})

    @action(detail=False, methods=['POST'])
    def chatgpt(self, request):
        data = request.data.copy()
        # Replace with your OpenAI API key
        # place_a = "Adimaly"
        # place_b = "Panickankudy"
        place_a = data.get('from')
        place_b = data.get('destination')
        UserSearches.objects.create(origin=place_a, destination=place_b, user=request.user)
        # prompt = f"I am seeking a list of tourist attractions situated between {place_a} and {place_b}." \
        #          f" These attractions should be relatively close to the mentioned locations and not far away." \
        #          f" Additionally, I would like the latitude and longitude coordinates for each attraction."
        # second = " the output should be like theis ['name, latitude, longitude', 'name, latitude, longitude'](give me the latitude and longitude in decimal degrees)"
        # prompt = prompt + second

        prompt = f"I'm looking for a compilation of tourist attractions located between {place_a} and {place_b} that are in close proximity to" \
                 f" these places. Furthermore, I'd like to receive the information for each attraction in a specific format. Each piece of" \
                 f" information should be structured as a dictionary with the following key-value pairs: 'name' for the attraction's name," \
                 f"'latitude' for its latitude coordinate in decimal degrees, and 'longitude' for its longitude coordinate in decimal degrees." \
                 f"This will provide me with an organized output that lists tourist attractions in the format:"

        prompt2 = "[{'name':'xyz', 'latitude':19837982374, 'longitude':00000}, {'name':'xyz', 'latitude':19837982374, 'longitude':00000}], with latitude and longitude coordinates expressed in decimal degrees"

        prompt = prompt + prompt2

        attractions_list = []
        try:
            result = openai.Completion.create(
                engine="text-davinci-003",  # Choose the engine that suits your needs
                prompt=prompt,
                max_tokens=200,
                api_key=config('CHAT_GPT_KEY')
            )
            lines = result.choices[0].text.strip().split('\n')
            result_string = result.choices[0].text.strip()
            start_index = result_string.find("[{")
            last_occurrence_index = result_string.rfind("},")
            if start_index != -1:
                list_str = result_string[start_index:last_occurrence_index] + "}]"
                attractions_list = eval(list_str)
                return response.Ok(attractions_list)
            # for line in lines:
            #     parts = line.split(', ')
            #     attr_dict = {'name': parts[0].split('. ')[-1], 'latitude': parts[1], 'longitude': parts[2]}
            #     attractions_list.append(attr_dict)
            # return response.Ok(attractions_list)
        except Exception as e:
            pass
        attractions_list = [{"name": "Tower of London", "latitude": 51.5081, "longitude": -0.0759},
                            {"name": "The Roman Baths, Bath", "latitude": 51.381, "longitude": -2.3597},
                            {"name": "Stonehenge", "latitude": 51.1789, "longitude": -1.8262},
                            {"name": "Liverpool Cathedral", "latitude": 53.4008, "longitude": -2.9782},
                            {"name": "The Alnwick Castle", "latitude": 55.4657, "longitude": -1.703}]
        return response.Ok(attractions_list)

    @action(detail=False, methods=['GET'])
    def user_searches(self, request):
        queryset = UserSearches.objects.filter(is_active=True)
        self.filterset_class = UserSearchesFilter
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(UserSearchesSerializer(page, many=True).data)
        return response.Ok(UserSearchesSerializer(queryset, many=True).data)
