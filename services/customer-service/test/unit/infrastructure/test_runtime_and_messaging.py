import importlib
import json
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from internal.application.errors import EventPublicationError
from internal.domain.events.customer_events import (
    CustomerInfoUpdated,
    CustomerRegistered,
)
from internal.infrastructure.config.settings import CustomerServiceSettings
from internal.infrastructure.messaging.factory import (
    create_event_publisher,
    open_rabbitmq_connection,
)
from internal.infrastructure.messaging.in_memory_event_publisher import (
    InMemoryEventPublisher,
)
from internal.infrastructure.messaging.rabbitmq_event_publisher import (
    RabbitMQEventPublisher,
)


def test_When_DatabaseUrlUsesSQLite_Expect_SettingsAcceptSupportedPersistenceModes() -> (  # noqa: E501
    None
):
    # Arrange / Act
    file_settings = CustomerServiceSettings(
        database_url="sqlite:///./customer-service.sqlite"
    )
    memory_settings = CustomerServiceSettings(database_url="sqlite://")

    # Assert
    assert file_settings.database_url == "sqlite:///./customer-service.sqlite"
    assert memory_settings.database_url == "sqlite://"


def test_When_DatabaseUrlUsesPostgres_Expect_SettingsRejectUnsupportedPersistence() -> (
    None
):
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="SQLite"):
        CustomerServiceSettings(
            database_url="postgresql://customer:secret@localhost:5432/customer"
        )


def test_When_MessagingBackendIsConfigured_Expect_FactoryReturnsExpectedPublisherType(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    opened_calls: list[dict[str, object]] = []
    rabbitmq_settings = CustomerServiceSettings(
        database_url="sqlite://",
        event_publisher_backend="rabbitmq",
        rabbitmq_url="amqp://guest:guest@localhost:5672/%2F",
    )
    in_memory_settings = CustomerServiceSettings(
        database_url="sqlite://",
        event_publisher_backend="in-memory",
    )
    monkeypatch.setattr(
        "internal.infrastructure.messaging.factory.open_rabbitmq_connection",
        lambda url, *, heartbeat, blocked_connection_timeout: (
            opened_calls.append(
                {
                    "url": url,
                    "heartbeat": heartbeat,
                    "blocked_connection_timeout": blocked_connection_timeout,
                }
            )
            or FakeBlockingConnection()
        ),
    )

    # Act
    rabbitmq_publisher = create_event_publisher(rabbitmq_settings)
    in_memory_publisher = create_event_publisher(in_memory_settings)

    # Assert
    assert isinstance(rabbitmq_publisher, RabbitMQEventPublisher)
    assert opened_calls == []
    assert isinstance(in_memory_publisher, InMemoryEventPublisher)


def test_When_PublishingCustomerLifecycleEvents_Expect_RabbitMqPayloadUsesCamelCaseJson() -> (  # noqa: E501
    None
):
    # Arrange
    opened_connections: list[FakeBlockingConnection] = []
    publisher = RabbitMQEventPublisher(
        connection_factory=lambda: (
            opened_connections.append(FakeBlockingConnection())
            or opened_connections[-1]
        ),
        exchange_name="customer.events",
    )
    registered_event = CustomerRegistered(
        customer_id=uuid4(),
        name="Jane Doe",
        email="jane@example.com",
        role="customer",
        registered_at=datetime(2026, 4, 21, tzinfo=UTC),
    )
    updated_event = CustomerInfoUpdated(
        customer_id=uuid4(),
        updated_fields=["name", "phone"],
    )

    # Act
    publisher.publish(registered_event)
    publisher.publish(updated_event)

    # Assert
    assert len(opened_connections) == 2
    assert opened_connections[0].closed is True
    assert opened_connections[1].closed is True
    assert opened_connections[0].channel_instance.exchange_declarations == [
        ("customer.events", "topic", True)
    ]
    assert opened_connections[0].channel_instance.published_messages[0][
        "routing_key"
    ] == ("CustomerRegistered")
    assert json.loads(
        opened_connections[0].channel_instance.published_messages[0]["body"]
    ) == {
        "customerId": str(registered_event.customer_id),
        "email": "jane@example.com",
        "eventName": "CustomerRegistered",
        "name": "Jane Doe",
        "registeredAt": "2026-04-21T00:00:00+00:00",
        "role": "customer",
    }
    assert json.loads(
        opened_connections[1].channel_instance.published_messages[0]["body"]
    ) == {
        "customerId": str(updated_event.customer_id),
        "eventName": "CustomerInfoUpdated",
        "updatedFields": ["name", "phone"],
    }


def test_When_ImportingMainEntrypoint_Expect_FastApiAppAvailableWithoutCmdCollision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("CUSTOMER_SERVICE_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("CUSTOMER_SERVICE_EVENT_PUBLISHER_BACKEND", "in-memory")
    sys.modules.pop("main", None)

    # Act
    main_module = importlib.import_module("main")
    stdlib_cmd = importlib.import_module("cmd")

    # Assert
    assert main_module.app.title == "Hotel DDD Customer Service API"
    assert hasattr(stdlib_cmd, "Cmd")


def test_When_FactoryReceivesUnsupportedBackend_Expect_ValueError() -> None:
    # Arrange
    settings = InvalidMessagingBackendSettings()

    # Act / Assert
    with pytest.raises(ValueError, match="Unsupported event publisher backend"):
        create_event_publisher(settings)


def test_When_OpeningRabbitMqConnection_Expect_UrlParametersPassedToPika(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_pika = FakePikaModule()
    monkeypatch.setitem(sys.modules, "pika", fake_pika)

    # Act
    connection = open_rabbitmq_connection(
        "amqp://guest:guest@localhost:5672/%2F",
        heartbeat=60,
        blocked_connection_timeout=30,
    )

    # Assert
    assert fake_pika.urls == ["amqp://guest:guest@localhost:5672/%2F"]
    assert connection.parameter.url == "amqp://guest:guest@localhost:5672/%2F"
    assert connection.parameter.heartbeat == 60
    assert connection.parameter.blocked_connection_timeout == 30


def test_When_ClosingRabbitMqPublisher_Expect_ConnectionClosed() -> None:
    # Arrange
    opened_connections: list[FakeBlockingConnection] = []
    publisher = RabbitMQEventPublisher(
        connection_factory=lambda: (
            opened_connections.append(FakeBlockingConnection())
            or opened_connections[-1]
        ),
        exchange_name="customer.events",
    )

    # Act
    publisher.close()

    # Assert
    assert opened_connections == []


def test_When_PublishingRabbitMqEvent_Expect_FactoryOpensConnectionPerPublish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    opened_connections: list[FakeBlockingConnection] = []
    settings = CustomerServiceSettings(
        database_url="sqlite://",
        event_publisher_backend="rabbitmq",
        rabbitmq_url="amqp://guest:guest@localhost:5672/%2F",
        rabbitmq_exchange="customer.events",
    )
    event = CustomerInfoUpdated(
        customer_id=uuid4(),
        updated_fields=["name"],
    )
    monkeypatch.setattr(
        "internal.infrastructure.messaging.factory.open_rabbitmq_connection",
        lambda url, *, heartbeat, blocked_connection_timeout: (
            opened_connections.append(FakeBlockingConnection())
            or opened_connections[-1]
        ),
    )
    publisher = create_event_publisher(settings)

    # Act
    publisher.publish(event)

    # Assert
    assert len(opened_connections) == 1
    assert opened_connections[0].closed is True
    assert opened_connections[0].channel_instance.exchange_declarations == [
        ("customer.events", "topic", True)
    ]


def test_When_RabbitMqPublishFails_Expect_ErrorLoggedAndPublicationError(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    connection = FakeBlockingConnection()
    connection.channel_instance.raise_on_publish = RuntimeError("broker unavailable")
    publisher = RabbitMQEventPublisher(
        connection_factory=lambda: connection,
        exchange_name="customer.events",
    )
    event = CustomerRegistered(
        customer_id=uuid4(),
        name="Jane Doe",
        email="jane@example.com",
        role="customer",
        registered_at=datetime(2026, 4, 21, tzinfo=UTC),
    )

    # Act / Assert
    with pytest.raises(
        EventPublicationError, match="Customer event publication failed"
    ):
        publisher.publish(event)

    assert connection.closed is True
    assert "Failed to publish customer event to RabbitMQ" in caplog.text
    assert "CustomerRegistered" in caplog.text


def test_When_PyrightIsConfigured_Expect_ServiceDeclaresTypeCheckingSettings() -> None:
    # Arrange
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"

    # Act
    pyproject = tomllib.loads(pyproject_path.read_text())

    # Assert
    assert "pyright>=1.1.0,<2.0.0" in pyproject["dependency-groups"]["dev"]
    assert pyproject["tool"]["pyright"] == {
        "include": ["internal", "main.py"],
        "venvPath": ".",
        "venv": ".venv",
        "typeCheckingMode": "basic",
    }


def test_When_CustomerServiceDocsAreRead_Expect_PyrightCommandIsDocumented() -> None:
    # Arrange
    docs_path = (
        Path(__file__).resolve().parents[5] / "docs/services/customer-service.md"
    )

    # Act
    documentation = docs_path.read_text()

    # Assert
    assert "`uv run pyright`" in documentation


def test_When_ValidationScriptIsRead_Expect_CanonicalQualityGateCommandsDefined() -> (
    None
):
    # Arrange
    script_path = Path(__file__).resolve().parents[3] / "scripts/validate.sh"

    # Act
    script = script_path.read_text()

    # Assert
    assert script.startswith("#!/usr/bin/env bash")
    assert "uv run ruff check ." in script
    assert "uv run black --check ." in script
    assert "uv run pyright" in script
    assert "uv run pytest --cov=internal --cov-report=term-missing" in script


def test_When_CustomerServiceDocsAreRead_Expect_CanonicalValidationCommandIsDocumented() -> (  # noqa: E501
    None
):
    # Arrange
    docs_path = (
        Path(__file__).resolve().parents[5] / "docs/services/customer-service.md"
    )

    # Act
    documentation = docs_path.read_text()

    # Assert
    assert "`./scripts/validate.sh`" in documentation
    assert "`uv run black --check .`" in documentation


def test_When_CustomerServiceDocsAreRead_Expect_InternalServerErrorAndBasicLoggingDocumented() -> (  # noqa: E501
    None
):
    # Arrange
    docs_path = (
        Path(__file__).resolve().parents[5] / "docs/services/customer-service.md"
    )

    # Act
    documentation = docs_path.read_text()

    # Assert
    assert "`500 Internal Server Error`" in documentation
    assert "logging básico" in documentation
    assert "register/login" in documentation
    assert "cambios de estado" in documentation


def test_When_DockerfileIsRead_Expect_UvRuntimeUsesServiceSourceAndPersistentDataDir() -> (  # noqa: E501
    None
):
    # Arrange
    dockerfile_path = Path(__file__).resolve().parents[3] / "Dockerfile"

    # Act
    dockerfile = dockerfile_path.read_text()

    # Assert
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert "COPY internal/ ./internal/" in dockerfile
    assert "COPY main.py ./" in dockerfile
    assert "mkdir -p data" in dockerfile
    assert "USER app" in dockerfile
    assert (
        '.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"'
        in dockerfile
    )


def test_When_DockerComposeFileIsRead_Expect_LocalStackWiresRabbitMqAndSqlitePersistence() -> (  # noqa: E501
    None
):
    # Arrange
    compose_path = Path(__file__).resolve().parents[5] / "docker-compose.yml"

    # Act
    compose = compose_path.read_text()

    # Assert
    assert "customer-service:" in compose
    assert "rabbitmq:" in compose
    assert "./services/customer-service/data:/app/data" in compose
    assert (
        "CUSTOMER_SERVICE_DATABASE_URL: sqlite:///./data/customer-service.sqlite"
        in compose
    )
    assert "CUSTOMER_SERVICE_EVENT_PUBLISHER_BACKEND: rabbitmq" in compose
    assert (
        "CUSTOMER_SERVICE_RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/%2F" in compose
    )


def test_When_DockerignoreIsRead_Expect_LocalVirtualenvCachesAndSqliteArtifactsIgnored() -> (  # noqa: E501
    None
):
    # Arrange
    dockerignore_path = Path(__file__).resolve().parents[3] / ".dockerignore"

    # Act
    dockerignore = dockerignore_path.read_text()

    # Assert
    assert ".venv/" in dockerignore
    assert "__pycache__/" in dockerignore
    assert ".pytest_cache/" in dockerignore
    assert "*.sqlite" in dockerignore


def test_When_CustomerServiceDocsAreRead_Expect_DockerComposeWorkflowIsDocumented() -> (  # noqa: E501
    None
):
    # Arrange
    docs_path = (
        Path(__file__).resolve().parents[5] / "docs/services/customer-service.md"
    )

    # Act
    documentation = docs_path.read_text()

    # Assert
    assert "docker compose up --build -d" in documentation
    assert "docker compose down" in documentation
    assert "`services/customer-service/data/`" in documentation
    assert "`http://localhost:8000/health`" in documentation


class FakeBlockingConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()
        self.closed = False

    def channel(self) -> "FakeChannel":
        return self.channel_instance

    def close(self) -> None:
        self.closed = True


class FakeUrlParameters:
    def __init__(self, url: str) -> None:
        self.url = url


class FakePikaModule:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def URLParameters(self, url: str) -> FakeUrlParameters:  # noqa: N802
        self.urls.append(url)
        return FakeUrlParameters(url)

    def BlockingConnection(  # noqa: N802
        self, parameter: FakeUrlParameters
    ) -> FakeBlockingConnection:
        return FakeBlockingConnectionWithParameter(parameter)


class FakeBlockingConnectionWithParameter(FakeBlockingConnection):
    def __init__(self, parameter: FakeUrlParameters) -> None:
        super().__init__()
        self.parameter = parameter


class InvalidMessagingBackendSettings:
    event_publisher_backend = "kafka"
    rabbitmq_url = "amqp://guest:guest@localhost:5672/%2F"
    rabbitmq_exchange = "customer.events"


class FakeChannel:
    def __init__(self) -> None:
        self.exchange_declarations: list[tuple[str, str, bool]] = []
        self.published_messages: list[dict[str, object]] = []
        self.raise_on_publish: Exception | None = None

    def exchange_declare(
        self, *, exchange: str, exchange_type: str, durable: bool
    ) -> None:
        self.exchange_declarations.append((exchange, exchange_type, durable))

    def basic_publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: str,
        properties: object,
    ) -> None:
        if self.raise_on_publish is not None:
            raise self.raise_on_publish
        self.published_messages.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
                "properties": properties,
            }
        )
