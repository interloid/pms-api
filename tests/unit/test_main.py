from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.main import app


def test_app_is_fastapi_instance():
    assert isinstance(app, FastAPI)


def test_app_metadata():
    assert app.title
    assert app.description
    assert app.version


def test_openapi_route_is_registered():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    assert app.openapi_url in paths


def test_docs_route_is_registered():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    assert app.docs_url in paths


def test_redoc_route_is_registered():
    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }

    assert app.redoc_url in paths


def test_api_routes_are_registered():
    api_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
    ]

    assert api_routes


def test_cors_middleware_is_registered():
    middleware_classes = [
        middleware.cls
        for middleware in app.user_middleware
    ]

    from starlette.middleware.cors import CORSMiddleware

    assert CORSMiddleware in middleware_classes


def test_logging_middleware_is_registered():
    middleware_classes = [
        middleware.cls
        for middleware in app.user_middleware
    ]

    from app.middleware.logging_middleware import LoggingMiddleware

    assert LoggingMiddleware in middleware_classes
    
    