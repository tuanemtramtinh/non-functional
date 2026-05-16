import logging
import re

from locust import HttpUser, LoadTestShape, between, events, task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------
TARGET_HOST = "https://tuanemtramtinhclone.moodlecloud.com"
USERNAME = "chaonhom"
PASSWORD = "sApTOIhanNopDA05"
QUIZ_CM_ID = 39  # id= trong URL /mod/quiz/view.php?id=39

# ---------------------------------------------------------------------------
# Performance SLOs
# ---------------------------------------------------------------------------
P95_SLO_MS = 3000  # P95 response time < 3 s
FAILURE_RATE_SLO = 5  # error rate < 5 %
MIN_RPS_SLO = 5  # throughput >= 5 req/s


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
# Quiz User — xem quiz rồi bắt đầu làm bài
# ===========================================================================


class MoodleQuizUser(HttpUser):
    """
    Mỗi virtual user:
      1. Đăng nhập (lấy logintoken CSRF + sesskey)
      2. Lặp lại: GET trang quiz → POST bắt đầu làm bài
      3. Đăng xuất khi kết thúc
    """

    host = TARGET_HOST
    wait_time = between(2, 5)

    def on_start(self):
        # Giả lập browser headers để tránh bị MoodleCloud chặn (403)
        self.client.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
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
    def view_and_attempt_quiz(self):
        """
        Luồng chính:
          1. GET /mod/quiz/view.php?id=39   — tải trang quiz
          2. POST /mod/quiz/startattempt.php — click "Attempt quiz now"
        """
        if not self._logged_in:
            self._login()
            return

        # Bước 3 — Mở trang xem quiz
        with self.client.get(
            "/mod/quiz/view.php",
            params={"id": QUIZ_CM_ID},
            catch_response=True,
            name="GET /mod/quiz/view.php?id=39",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Quiz view thất bại: {resp.status_code}")
                return
            if "quiz" not in resp.text.lower():
                resp.failure("Trang quiz không tải đúng nội dung")
                return
            if resp.elapsed.total_seconds() * 1000 > P95_SLO_MS:
                resp.failure(
                    f"Quiz view quá chậm: {resp.elapsed.total_seconds() * 1000:.0f} ms"
                )
            # Lấy sesskey trực tiếp từ trang quiz (an toàn hơn dùng sesskey từ login)
            page_sesskey = _scrape_hidden(resp.text, "sesskey") or self._sesskey

        # Bước 4 — POST bắt đầu làm bài (tương đương click "Attempt quiz now")
        # Moodle sẽ redirect đến /mod/quiz/attempt.php?attempt=X&cmid=39
        with self.client.post(
            "/mod/quiz/startattempt.php",
            data={
                "sesskey": page_sesskey,
                "cmid": str(QUIZ_CM_ID),
                "forcenew": "0",
            },
            catch_response=True,
            allow_redirects=True,
            name="POST /mod/quiz/startattempt.php",
        ) as resp:
            if resp.status_code not in (200, 303):
                resp.failure(f"Bắt đầu làm bài thất bại: {resp.status_code}")
            elif "loginerrormessage" in resp.text:
                resp.failure("Session hết hạn khi bắt đầu làm bài")
                self._logged_in = False
            elif "quizpassword" in resp.text:
                resp.failure("Quiz yêu cầu mật khẩu — id=63 phải là no-password quiz")
            elif "nomoreattempts" in resp.text or "No more attempts" in resp.text:
                resp.failure("Đã hết lượt làm bài")
            elif "attempt.php" not in resp.url:
                # TC002003: assertRegex(current_url, r"attempt\.php\?attempt=\d+&cmid=\d+")
                resp.failure(
                    f"Không redirect đến attempt.php — URL thực tế: {resp.url}"
                )
            elif resp.elapsed.total_seconds() * 1000 > P95_SLO_MS:
                resp.failure(
                    f"Start attempt quá chậm: {resp.elapsed.total_seconds() * 1000:.0f} ms"
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
    """In kết quả pass/fail và set exit code 1 nếu vi phạm SLO."""
    stats = environment.runner.stats.total
    p95_ms = stats.get_response_time_percentile(0.95) or 0
    failure_pct = (
        (stats.num_failures / stats.num_requests * 100) if stats.num_requests else 0
    )
    rps = stats.current_rps

    sep = "=" * 65
    logger.info(sep)
    logger.info("  MOODLE QUIZ PERFORMANCE TEST — FINAL RESULTS")
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
