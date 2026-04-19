---
name: hotel-architecture-boundaries
description: >
  Define los límites de arquitectura del monorepo para evitar mezclar bounded
  contexts y compartir lógica de dominio incorrectamente. Trigger: cuando el agente
  vaya a crear, mover o revisar código entre servicios.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Cuando se agregue código a un microservicio
- Cuando se quiera reutilizar algo en `shared/`
- Cuando se revisen cambios estructurales del monorepo

## Critical Patterns

- Cada microservicio mantiene su propio dominio
- `shared/contracts` es para contratos de integración, no para reglas de negocio
- `shared/test-kit` es para utilidades de testing, no para dominio compartido
- No mover entidades, value objects o políticas de negocio a `shared/`
- Respetar la separación `domain`, `application`, `infrastructure`, `interfaces`

## Decision Table

| Caso | Ubicación correcta |
| --- | --- |
| Entidad o value object de un servicio | `services/<service>/internal/domain/...` |
| Caso de uso | `services/<service>/internal/application/usecases` |
| Adaptador HTTP o mensajería | `services/<service>/internal/infrastructure` o `interfaces` |
| Helper de testing reutilizable | `shared/test-kit` |
| Contrato de integración | `shared/contracts` |

## Code Examples

```text
Correcto: services/booking-service/internal/domain/entities/reservation.go
Incorrecto: shared/building-blocks/reservation.go
```

## Commands

```bash
git diff
git status
```

## Resources

- `README.md`
- `AGENTS.md`
