import logging
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
}


class ApiError(BaseModel):
    code: str = Field(description="Mã lỗi ổn định để frontend/client xử lý")
    message: str = Field(description="Thông báo lỗi dành cho người dùng")
    details: Any | None = Field(default=None, description="Chi tiết lỗi nếu có")
    request_id: str = Field(description="Mã truy vết request")


class V1ApiError(BaseModel):
    """Error contract dành riêng cho các endpoint `/api/v1`."""

    code: str = Field(description="Mã lỗi ổn định để frontend/client xử lý")
    message: str = Field(description="Thông báo lỗi dành cho người dùng")
    details: dict[str, Any] | None = Field(
        default=None, description="Chi tiết lỗi dạng object nếu có"
    )
    request_id: str = Field(description="Mã truy vết request")


V1_ERROR_RESPONSES: dict[str, dict[str, Any]] = {
    "400": {
        "description": "Yêu cầu không hợp lệ",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "401": {
        "description": "Chưa xác thực",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "403": {
        "description": "Không có quyền",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "404": {
        "description": "Không tìm thấy tài nguyên",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "409": {
        "description": "Xung đột dữ liệu",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "422": {
        "description": "Dữ liệu không hợp lệ",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "429": {
        "description": "Vượt giới hạn truy cập",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
    "500": {
        "description": "Lỗi hệ thống",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/V1ApiError"}}},
    },
}


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    request_id = request.headers.get("X-Request-ID", "")
    return request_id if REQUEST_ID_PATTERN.fullmatch(request_id) else uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        requested_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            requested_id if REQUEST_ID_PATTERN.fullmatch(requested_id) else uuid4().hex
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ApiError(
        code=code,
        message=message,
        details=details,
        request_id=get_request_id(request),
    )
    response = JSONResponse(status_code=status_code, content=jsonable_encoder(payload))
    if headers:
        for name, value in headers.items():
            response.headers[name] = value
    response.headers["X-Request-ID"] = payload.request_id
    return response


def _v1_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = V1ApiError(
        code=code,
        message=message,
        details=details,
        request_id=get_request_id(request),
    )
    response = JSONResponse(status_code=status_code, content=jsonable_encoder(payload))
    if headers:
        for name, value in headers.items():
            response.headers[name] = value
    response.headers["X-Request-ID"] = payload.request_id
    return response


def _is_v1_path(path: str) -> bool:
    return path == "/api/v1" or path.startswith("/api/v1/")


def _v1_detail_parts(
    detail: Any, status_code: int
) -> tuple[str, str, dict[str, Any] | None]:
    if isinstance(detail, dict):
        code = str(detail.get("code") or ERROR_CODES.get(status_code, "http_error"))
        message = str(detail.get("message") or "Yêu cầu không thể được xử lý")
        nested_details = detail.get("details")
        if isinstance(nested_details, dict):
            return code, message, nested_details
        if "code" not in detail and "message" not in detail:
            return code, message, detail
        return code, message, None
    return (
        ERROR_CODES.get(status_code, "http_error"),
        str(detail) if detail else "Yêu cầu không thể được xử lý",
        None,
    )


async def http_exception_handler(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    if _is_v1_path(request.url.path):
        code, message, details = _v1_detail_parts(exc.detail, exc.status_code)
        return _v1_error_response(
            request,
            exc.status_code,
            code,
            message,
            details,
            dict(exc.headers or {}),
        )

    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or ERROR_CODES.get(exc.status_code, "http_error"))
        message = str(detail.get("message") or "Yêu cầu không thể được xử lý")
        details = detail.get("details")
    else:
        code = ERROR_CODES.get(exc.status_code, "http_error")
        message = str(detail) if detail else "Yêu cầu không thể được xử lý"
        details = None
    return _error_response(
        request,
        exc.status_code,
        code,
        message,
        details,
        dict(exc.headers or {}),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if _is_v1_path(request.url.path):
        return _v1_error_response(
            request,
            422,
            "validation_error",
            "Dữ liệu gửi lên không hợp lệ",
            {"errors": exc.errors()},
        )

    return _error_response(
        request,
        422,
        "validation_error",
        "Dữ liệu gửi lên không hợp lệ",
        exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception request_id=%s", get_request_id(request), exc_info=exc)
    if _is_v1_path(request.url.path):
        return _v1_error_response(
            request,
            500,
            "internal_error",
            "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
        )

    return _error_response(
        request,
        500,
        "internal_error",
        "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
    )


def install_http_contract(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {}).update(
            {
                "CookieAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "hrms_access_token",
                    "description": "Session HttpOnly cookie; luồng xác thực chính.",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Deprecated: compatibility fallback cho client cũ.",
                },
            }
        )
        components["securitySchemes"].pop("HTTPBearer", None)
        components.setdefault("schemas", {})[
            "ApiError"
        ] = ApiError.model_json_schema(ref_template="#/components/schemas/{model}")
        components["schemas"]["V1ApiError"] = V1ApiError.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        error_responses = {
            "400": "Yêu cầu không hợp lệ",
            "401": "Chưa xác thực",
            "403": "Không có quyền",
            "404": "Không tìm thấy tài nguyên",
            "409": "Xung đột dữ liệu",
            "422": "Dữ liệu không hợp lệ",
            "429": "Vượt giới hạn truy cập",
            "500": "Lỗi hệ thống",
        }
        legacy_error_schema = {"$ref": "#/components/schemas/ApiError"}
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict) or "responses" not in operation:
                    continue
                if path.startswith("/api/") and not path.startswith("/api/v1/"):
                    operation["deprecated"] = True
                if operation.get("security"):
                    operation["security"] = [{"CookieAuth": []}, {"BearerAuth": []}]
                if method.lower() in {"post", "put", "patch", "delete"} and not path.endswith(
                    "/auth/login"
                ):
                    parameters = operation.setdefault("parameters", [])
                    if not any(
                        parameter.get("name") == "Idempotency-Key"
                        for parameter in parameters
                        if isinstance(parameter, dict)
                    ):
                        parameters.append(
                            {
                                "name": "Idempotency-Key",
                                "in": "header",
                                "required": False,
                                "schema": {"type": "string", "maxLength": 255},
                                "description": "Tùy chọn: khóa chống xử lý lặp cho request ghi.",
                            }
                        )
                if _is_v1_path(path):
                    operation["responses"].update(V1_ERROR_RESPONSES)
                else:
                    for status_code, description in error_responses.items():
                        operation["responses"][status_code] = {
                            "description": description,
                            "content": {"application/json": {"schema": legacy_error_schema}},
                        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
