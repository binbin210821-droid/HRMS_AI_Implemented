import argparse
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test dữ liệu nền và RBAC Phase 3")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def request_json(
    base_url: str, path: str, token: str | None = None, method: str = "GET", body=None
):
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = Request(f"{base_url}{path}", headers=headers, method=method, data=data)
    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except HTTPError as error:
        payload = error.read()
        return error.code, json.loads(payload) if payload else None


def login(base_url: str, username: str, password: str) -> str:
    status, response = request_json(
        base_url,
        "/api/v1/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )
    assert status == 200, response
    return response["access_token"]


if __name__ == "__main__":
    args = parse_args()
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    sales_token = login(args.base_url, "demo.manager", args.password)
    tech_token = login(args.base_url, "demo.manager.tech", args.password)

    status, departments_page = request_json(
        args.base_url,
        "/api/v1/departments?page=1&page_size=100",
        leadership_token,
    )
    assert status == 200 and departments_page["items"], departments_page
    departments = departments_page["items"]
    assert departments_page["has_next"] is False, departments_page
    department_by_code = {department["code"]: department for department in departments}

    status, leadership_page = request_json(args.base_url, "/api/v1/employees?page_size=100", leadership_token)
    leadership_employees = leadership_page["items"]
    assert status == 200 and len(leadership_employees) >= 15, leadership_page

    status, sales_page = request_json(args.base_url, "/api/v1/employees?page_size=100", sales_token)
    sales_employees = sales_page["items"]
    assert status == 200 and sales_employees, sales_page
    assert all(
        employee["department_id"] == department_by_code["KD"]["id"] for employee in sales_employees
    )

    status, tech_page = request_json(args.base_url, "/api/v1/employees?page_size=100", tech_token)
    tech_employees = tech_page["items"]
    assert status == 200 and tech_employees, tech_page
    assert all(
        employee["department_id"] == department_by_code["KT"]["id"] for employee in tech_employees
    )

    tech_query = urlencode({"department_id": department_by_code["KT"]["id"]})
    status, filtered_page = request_json(
        args.base_url, f"/api/v1/employees?{tech_query}", sales_token
    )
    filtered_by_manager = filtered_page["items"]
    assert status == 200
    assert all(
        employee["department_id"] == department_by_code["KD"]["id"]
        for employee in filtered_by_manager
    )

    status, forbidden_department_write = request_json(
        args.base_url,
        "/api/v1/departments",
        sales_token,
        method="POST",
        body={"name": "Không được tạo", "code": "NOPE"},
    )
    assert status == 403, forbidden_department_write

    test_department_code = f"QA{int(time.time()) % 100000}"
    status, created_department = request_json(
        args.base_url,
        "/api/v1/departments",
        leadership_token,
        method="POST",
        body={"name": "Phòng kiểm thử", "code": test_department_code},
    )
    assert status == 201, created_department
    status, updated_department = request_json(
        args.base_url,
        f"/api/v1/departments/{created_department['id']}",
        leadership_token,
        method="PATCH",
        body={"name": "Phòng kiểm thử đã cập nhật"},
    )
    assert status == 200 and updated_department["name"] == "Phòng kiểm thử đã cập nhật"
    status, _ = request_json(
        args.base_url,
        f"/api/v1/departments/{created_department['id']}",
        leadership_token,
        method="DELETE",
    )
    assert status == 204

    test_employee_code = f"QA-NV-{int(time.time()) % 100000}"
    status, created_employee = request_json(
        args.base_url,
        "/api/v1/employees",
        sales_token,
        method="POST",
        body={
            "employee_code": test_employee_code,
            "full_name": "Nhân viên kiểm thử",
            "position": "Chuyên viên",
            "department_id": department_by_code["KD"]["id"],
        },
    )
    assert status == 201, created_employee
    status, updated_employee = request_json(
        args.base_url,
        f"/api/v1/employees/{created_employee['id']}",
        sales_token,
        method="PATCH",
        body={"position": "Chuyên viên cập nhật"},
    )
    assert status == 200 and updated_employee["position"] == "Chuyên viên cập nhật"
    status, _ = request_json(
        args.base_url,
        f"/api/v1/employees/{created_employee['id']}",
        sales_token,
        method="DELETE",
    )
    assert status == 204

    tech_employee_id = tech_employees[0]["id"]
    status, cross_department_employee = request_json(
        args.base_url, f"/api/v1/employees/{tech_employee_id}", sales_token
    )
    assert status == 404, cross_department_employee

    print("Phase 3 smoke test passed: seed, role scope và department RBAC.")
