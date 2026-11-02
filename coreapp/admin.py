from django.contrib import admin

from .models import RegistroAuditoria


class ActorAuditoriaFilter(admin.SimpleListFilter):
    title = "actor (referencia técnica)"
    parameter_name = "actor"

    def lookups(self, request, model_admin):
        ids = model_admin.get_queryset(request).order_by().values_list("usuario_id", flat=True).distinct()
        return [
            (str(pk), f"Cuenta {pk}") if pk is not None else ("sin_actor", "Sin actor identificado")
            for pk in ids
        ]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == "sin_actor":
            return queryset.filter(usuario__isnull=True)
        if valor:
            if not valor.isascii() or not valor.isdigit() or len(valor) > 19 or int(valor) > 2**63 - 1:
                return queryset.none()
            return queryset.filter(usuario_id=valor)
        return queryset


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "creado_en", "accion", "actor_tecnico", "objeto_tipo", "objeto_id")
    list_display_links = ("id",)
    list_filter = ("accion", "creado_en", ActorAuditoriaFilter)
    search_fields = ("=objeto_tipo", "=objeto_id")
    date_hierarchy = "creado_en"
    fields = readonly_fields = ("id", "creado_en", "accion", "actor_tecnico", "objeto_tipo", "objeto_id")
    actions = None

    @admin.display(description="Actor")
    def actor_tecnico(self, obj):
        return f"Cuenta {obj.usuario_id}" if obj.usuario_id is not None else "Sin actor identificado"

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if self.has_view_permission(request) else queryset.none()
