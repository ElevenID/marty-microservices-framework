# Framework Modules Overview

This document provides an overview of the core modules available in the Marty Microservices Framework (`mmf/framework`).

## Machine Learning (`mmf/framework/ml`)

Provides a hexagonal architecture implementation of ML components.

*   **Key Features**:
    *   Feature Store
    *   Model Registry
    *   Model Serving
    *   A/B Testing Experiments

## Workflow Engine (`mmf/framework/workflow`)

Provides workflow orchestration and saga pattern support.

*   **Key Features**:
    *   Workflow Engine for orchestrating steps
    *   State management (WorkflowContext, WorkflowStatus)
    *   Step execution and result handling

## Architectural Patterns (`mmf/framework/patterns`)

Provides advanced architectural patterns for building robust, scalable microservices.

*   **Key Features**:
    *   **Event Sourcing**: AggregateRoot, EventSourcedRepository, SnapshotStore
    *   **Saga Pattern**: SagaManager, SagaOrchestrator, CompensationAction
    *   **CQRS**: Command Query Responsibility Segregation patterns
    *   **Distributed Transactions**: Support for complex distributed workflows
