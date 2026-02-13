# Integration Testing Patterns for ZeroTouch Engine

## Core Philosophy

**"Test Real Infrastructure, Mock External Dependencies, Use Production Code Paths"**

**Critical Principle: Same Code Paths as Production**
- Tests must use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior
