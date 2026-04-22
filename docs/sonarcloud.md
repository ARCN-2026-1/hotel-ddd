# SonarCloud

## Qué hace

Análisis estático de código que corre automáticamente en:

- cada push a `develop`
- cada push a `main`

Los Pull Requests siguen validando calidad en `.github/workflows/ci.yml`; SonarCloud queda reservado para pushes a ramas protegidas.

## Archivos involucrados

- `sonar-project.properties` — configuración del proyecto (organización, fuentes, exclusiones, patrones de test y coverage)
- `.github/workflows/sonar.yml` — workflow que dispara el análisis y genera coverage real para `customer-service`

## Requisitos

El secret `SONAR_TOKEN` debe estar configurado en GitHub.

## Métricas objetivo

- Bugs: 0
- Vulnerabilidades: 0
- Cobertura mínima: 70% sobre código nuevo (cuando haya tests y reportes de coverage)

## Protección de ramas

La estrategia actual separa validación de PR y análisis SonarCloud:

- **PR hacia `develop`**: validar con `.github/workflows/ci.yml`
- **Push a `develop` y `main`**: ejecutar SonarCloud

### Recomendación para `develop`

- Require a pull request before merging
- Require status checks to pass before merging
- Seleccionar `Customer Service Quality` como check obligatorio

### Recomendación para `main`

- Require a pull request before merging
- Require status checks to pass before merging
- Mantener `SonarCloud Scan` como check obligatorio si se quiere usar `main` como validación final de calidad integrada

## Coverage

SonarCloud no genera cobertura — solo consume reportes que produce el pipeline de tests.

El camino para activarla:

1. Crear pipeline de tests por servicio
2. Generar reportes de cobertura en CI
3. Apuntar `sonar-project.properties` al reporte generado
4. Exigir cobertura mínima en el Quality Gate

Reporte actual configurado:

- `services/customer-service/coverage.xml`

## Flujo actual resumido

- `ci.yml` corre en Pull Requests hacia `develop` con Ruff, Black, Pyright y pytest
- `sonar.yml` corre solo en pushes a `develop` y `main`
- Esto evita depender de branch analysis de SonarCloud en feature branches, que no está disponible en el plan actual
