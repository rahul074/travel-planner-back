import inspect
from functools import reduce

from rest_framework.permissions import BasePermission

class ResourcePermission(BasePermission):
    enough_perms = None
    global_perms = None
    partial_update_perms = None
    retrieve_perms = None
    create_perms = None
    update_perms = None
    destroy_perms = None
    list_perms = None

    def has_action_permission(self, request, view, action, obj=None):
        permset = getattr(self, "{}_perms".format(action))

        if isinstance(permset, (list, tuple)):
            permset = reduce(lambda acc, v: acc & v, permset)
        elif permset is None:
            # Use empty operator that always return true with
            # empty components.
            permset = And()
        elif isinstance(permset, PermissionComponent):
            # Do nothing
            pass
        elif inspect.isclass(permset) and issubclass(permset, PermissionComponent):
            permset = permset()
        else:
            raise RuntimeError("Invalid permission definition.")

        if self.global_perms:
            permset = (self.global_perms & permset)

        if self.enough_perms:
            permset = (self.enough_perms | permset)

        if obj is None:
            return permset.has_permission(request=request, view=view)

        return permset.has_object_permission(request=request, view=view, obj=obj)


class PermissionComponent(object):

    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

    def __invert__(self):
        return Not(self)

    def __and__(self, component):
        return And(self, component)

    def __or__(self, component):
        return Or(self, component)


class PermissionOperator(PermissionComponent):
    def __init__(self, *components):
        self.components = tuple(components)


class Not(PermissionOperator):
    def __init__(self, component):
        super(Not, self).__init__(component)

    def has_permission(self, *args, **kwargs):
        component = sq.first(self.components)
        return (not component.has_permission(*args, **kwargs))

    def has_object_permission(self, *args, **kwargs):
        component = sq.first(self.components)
        return (not component.has_object_permission(*args, **kwargs))


class Or(PermissionOperator):
    def has_permission(self, *args, **kwargs):
        valid = False

        for component in self.components:
            if component.has_permission(*args, **kwargs):
                valid = True
                break

        return valid

    def has_object_permission(self, *args, **kwargs):
        valid = False

        for component in self.components:
            if component.has_object_permission(*args, **kwargs):
                valid = True
                break

        return valid


class And(PermissionOperator):
    def has_permission(self, *args, **kwargs):
        valid = True

        for component in self.components:
            if not component.has_permission(*args, **kwargs):
                valid = False
                break

        return valid

    def has_object_permission(self, *args, **kwargs):
        valid = True

        for component in self.components:
            if not component.has_object_permission(*args, **kwargs):
                valid = False
                break

        return valid


class AllowAny(PermissionComponent):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return True


class DenyAll(PermissionComponent):
    def has_permission(self, request, view):
        return False

    def has_object_permission(self, request, view, obj):
        return False


class IsAuthenticated(PermissionComponent):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated()

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated()


class IsSuperUser(PermissionComponent):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated() and request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated() and request.user.is_superuser


class HasMandatoryParam(PermissionComponent):
    def __init__(self, param, *components):
        self.mandatory_param = param
        super(HasMandatoryParam, self).__init__(*components)

    def has_permission(self, request, view):
        param = request.GET.get(self.mandatory_param, None)
        if param:
            return True
        return False


class IsObjectOwner(PermissionComponent):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class AdminPerm(PermissionComponent):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class UserPerm(PermissionComponent):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and not request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and not request.user.is_superuser
