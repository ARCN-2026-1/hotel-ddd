# Sistema de Gestión de Reservas de Hotel

## Descripción

Monorepo para un sistema de reservas de hotel, modelado con DDD y separado en microservicios por bounded context.

## Objetivo

Cubrir los procesos principales de reserva de habitaciones:

- creación y cancelación de reservas
- validación de disponibilidad
- gestión de clientes
- procesamiento de pagos

## Estructura del repositorio

```
services/       microservicios del sistema
docs/           documentación del proyecto
shared/         contratos y utilidades compartidas
deploy/         archivos de despliegue local
.github/        plantillas y workflows de CI
```

## Microservicios

| Servicio | Responsabilidad |
| --- | --- |
| `booking-service` | Ciclo de vida de las reservas |
| `inventory-service` | Habitaciones y disponibilidad |
| `customer-service` | Clientes y su estado |
| `payment-service` | Pagos y reembolsos |

## Documentación

| Documento | Propósito |
| --- | --- |
| `docs/git-workflow.md` | Flujo de trabajo con Git: ramas, convenciones, merge |
| `docs/sonarcloud.md` | Configuración y uso de SonarCloud en el repo |
| `docs/ddd/DDD.pdf` | Modelo de dominio inicial |
| `.github/pull_request_template.md` | Plantilla común para Pull Requests |

## Flujo de trabajo

El equipo trabaja con `main` y `develop`, usando ramas temporales por tarea. Los detalles están en `docs/git-workflow.md`.

## Estado actual

- Estructura base del monorepo armada
- Documentación de flujo Git y plantilla de PR
- SonarCloud configurado como check de calidad
- Modelo de dominio inicial disponible

## Próximos pasos

- Definir la configuración base de cada servicio
- Implementar los primeros casos de uso
- Agregar pipeline de tests y cobertura
