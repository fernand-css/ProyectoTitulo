"""La escritura de farmacia se realiza exclusivamente por servicios auditados.

Los modelos de dominio no se registran en Admin: tampoco existen acciones
masivas que eludan permisos, historial o cupo. La auditoría genérica conserva
su administrador de consulta del núcleo.
"""
