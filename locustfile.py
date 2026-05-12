import logging
import random
import re

from locust import HttpUser, LoadTestShape, between, events, task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------
TARGET_HOST = "https://school.moodledemo.net"
USERNAME = "manager"
PASSWORD = "moodle26"

# ---------------------------------------------------------------------------
# Performance SLOs
# ---------------------------------------------------------------------------
P95_SLO_MS = 3000  # 95th-percentile response time < 3 s
FAILURE_RATE_SLO = 5  # error rate < 5 %
MIN_RPS_SLO = 5  # system must sustain >= 5 req/s


# ===========================================================================
# Helpers
# ===========================================================================


def _scrape_hidden(html: str, name: str) -> str:
    """Extract a hidden input value from raw HTML by field name."""
    match = re.search(
        rf'<input[^>]+name=["\']?{re.escape(name)}["\']?[^>]+value=["\']([^"\']*)["\']',
        html,
    ) or re.search(
        rf'<input[^>]+value=["\']([^"\']*)["\'][^>]+name=["\']?{re.escape(name)}["\']?',
        html,
    )
    return match.group(1) if match else ""


# ===========================================================================
# Manager User — chỉ tạo khoá học mới
# ===========================================================================


class MoodleManagerUser(HttpUser):
    """
    Mỗi virtual user:
      1. Đăng nhập (lấy logintoken CSRF)
      2. Lặp lại: mở form → submit tạo khoá học mới
      3. Đăng xuất khi kết thúc
    """

    host = TARGET_HOST
    wait_time = between(2, 5)

    def on_start(self):
        self._sesskey = ""
        self._logged_in = False
        self._login()

    def on_stop(self):
        if self._logged_in:
            self.client.get(
                "/login/logout.php",
                params={"sesskey": self._sesskey},
                name="GET /logout",
                allow_redirects=True,
            )

    def _login(self):
        # Bước 1 — GET trang login để lấy logintoken
        with self.client.get(
            "/login/index.php",
            catch_response=True,
            name="GET /login (token fetch)",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Login page unreachable: {resp.status_code}")
                return
            logintoken = _scrape_hidden(resp.text, "logintoken")

        # Bước 2 — POST đăng nhập
        with self.client.post(
            "/login/index.php",
            data={
                "username": USERNAME,
                "password": PASSWORD,
                "logintoken": logintoken,
                "anchor": "",
            },
            catch_response=True,
            allow_redirects=True,
            name="POST /login",
        ) as resp:
            if "loginerrormessage" in resp.text or resp.status_code >= 400:
                resp.failure("Login failed — sai tài khoản hoặc lỗi server")
                return
            self._sesskey = (
                _scrape_hidden(resp.text, "sesskey")
                or (re.search(r'"sesskey"\s*:\s*"([^"]+)"', resp.text) or ["", ""])[1]
            )
            self._logged_in = True

    @task
    def create_course(self):
        """
        Luồng đầy đủ tạo khoá học:
          1. GET /course/edit.php?category=0  — mở form
          2. POST /course/edit.php            — submit form
        """
        if not self._logged_in:
            self._login()
            return

        # Bước 1 — Mở form tạo khoá học
        with self.client.get(
            "/course/edit.php",
            params={"category": 0},
            catch_response=True,
            name="GET /course/edit.php?category=0",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Mở form thất bại: {resp.status_code}")
                return
            if "fullname" not in resp.text:
                resp.failure("Form không tải đúng nội dung")
                return
            if resp.elapsed.total_seconds() * 1000 > P95_SLO_MS:
                resp.failure(
                    f"Form load quá chậm: {resp.elapsed.total_seconds() * 1000:.0f} ms"
                )

        # Bước 2 — Submit tạo khoá học
        unique_id = random.randint(100000, 999999)
        course_name = f"Perf Test Course {unique_id}"
        shortname = f"PTC{unique_id}"

        with self.client.post(
            "/course/edit.php",
            data={
                # CSRF + form identifier (bắt buộc để Moodle nhận đây là form submit)
                "sesskey": self._sesskey,
                "_qf__course_edit_form": "1",
                "mform_isexpanded_id_generalhdr": "1",
                # Thông tin khoá học
                "fullname": course_name,
                "shortname": shortname,
                "idnumber": "",
                "category": "1",
                "visible": "1",
                "downloadcontent": "1",
                # Ngày bắt đầu
                "startdate[day]": "1",
                "startdate[month]": "1",
                "startdate[year]": "2025",
                "startdate[hour]": "0",
                "startdate[minute]": "0",
                # Ngày kết thúc (disabled)
                "enddate[enabled]": "0",
                "enddate[day]": "1",
                "enddate[month]": "1",
                "enddate[year]": "2026",
                "enddate[hour]": "0",
                "enddate[minute]": "0",
                # Mô tả
                "summary_editor[text]": f"Locust perf test {unique_id}",
                "summary_editor[format]": "1",
                # Định dạng khoá học
                "format": "topics",
                "numsections": "5",
                "hiddensections": "0",
                "coursedisplay": "0",
                # Điểm + báo cáo
                "showgrades": "1",
                "showreports": "0",
                # Hoàn thành
                "enablecompletion": "1",
                "showcompletionconditions": "1",
                # Submit
                "returnto": "topcat",
                "saveanddisplay": "Save and display",
            },
            catch_response=True,
            allow_redirects=True,
            name="POST /course/edit.php (tạo khoá học)",
        ) as resp:
            if resp.status_code not in (200, 303):
                resp.failure(f"Tạo khoá học thất bại: {resp.status_code}")
            elif "loginerrormessage" in resp.text:
                resp.failure("Session hết hạn khi tạo khoá học")
                self._logged_in = False
            elif "id_error_fullname" in resp.text or "id_error_shortname" in resp.text:
                resp.failure("Form validation error — khoá học không được tạo")
            elif resp.elapsed.total_seconds() * 1000 > P95_SLO_MS:
                resp.failure(
                    f"Submit quá chậm: {resp.elapsed.total_seconds() * 1000:.0f} ms"
                )


# ===========================================================================
# Stair-step Load Shape — tăng tải 3 bậc trong 3 phút
# ===========================================================================


class StairStepShape(LoadTestShape):
    """
    Stage | Duration  | Users | Spawn Rate
    ------|-----------|-------|----------
      1   |  0–60 s   |   5   |     2     ← warm-up
      2   | 60–120 s  |  20   |     5     ← tăng tải
      3   | 120–180 s |  50   |    10     ← stress
    """

    stages = [
        {"duration": 60, "users": 5, "spawn_rate": 2},
        {"duration": 120, "users": 20, "spawn_rate": 5},
        {"duration": 180, "users": 50, "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None


# ===========================================================================
# Post-test SLO validation
# ===========================================================================


@events.quitting.add_listener
def validate_slos(environment, **kwargs):
    """Print a pass/fail verdict and set exit code 1 if any SLO is breached."""
    stats = environment.runner.stats.total
    p95_ms = stats.get_response_time_percentile(0.95) or 0
    failure_pct = (
        (stats.num_failures / stats.num_requests * 100) if stats.num_requests else 0
    )
    rps = stats.current_rps

    sep = "=" * 65
    logger.info(sep)
    logger.info("  MOODLE PERFORMANCE TEST — FINAL RESULTS")
    logger.info(sep)
    logger.info(f"  Total requests      : {stats.num_requests}")
    logger.info(f"  Total failures      : {stats.num_failures}")
    logger.info(
        f"  Failure rate        : {failure_pct:.2f}%    (SLO < {FAILURE_RATE_SLO}%)"
    )
    logger.info(f"  P95 response time   : {p95_ms:.0f} ms  (SLO < {P95_SLO_MS} ms)")
    logger.info(f"  Current throughput  : {rps:.2f} req/s  (SLO >= {MIN_RPS_SLO})")
    logger.info(sep)

    breaches = []
    if p95_ms > P95_SLO_MS:
        breaches.append(f"P95 {p95_ms:.0f} ms > SLO {P95_SLO_MS} ms")
    if failure_pct > FAILURE_RATE_SLO:
        breaches.append(f"Failure rate {failure_pct:.2f}% > SLO {FAILURE_RATE_SLO}%")
    if rps < MIN_RPS_SLO:
        breaches.append(f"Throughput {rps:.2f} RPS < SLO {MIN_RPS_SLO} RPS")

    if breaches:
        logger.warning("  [FAIL] PERFORMANCE OBJECTIVES NOT MET:")
        for b in breaches:
            logger.warning(f"         • {b}")
        environment.process_exit_code = 1
    else:
        logger.info("  [PASS] All performance objectives met.")
    logger.info(sep)
