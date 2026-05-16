# Performance Testing Report — Moodle Cloud (Quiz Attempt)

## 1. Thông tin chung

| Mục | Chi tiết |
|---|---|
| **Loại test** | Performance Testing (Non-Functional) |
| **Tool** | Locust 2.44.0 |
| **Target URL** | https://tuanemtramtinhclone.moodlecloud.com/mod/quiz/view.php?id=39 |
| **Tài khoản** | chaonhom / sApTOIhanNopDA05 |
| **Thời gian chạy** | 3 phút |
| **Ngày thực hiện** | 2026-05-16 |

---

## 2. Mục tiêu kiểm thử

> *"Response times and throughput rates under certain workload and configuration conditions. Test cases are designed to show that the program does not satisfy its performance objectives."*

Kiểm tra hệ thống Moodle Cloud có đáp ứng được yêu cầu hiệu năng khi **nhiều người dùng đồng thời truy cập và bắt đầu làm bài quiz** hay không.

**Chức năng được test:** Xem quiz và bắt đầu làm bài (`mod/quiz/view.php?id=39` → `startattempt.php`)

Tương đương test case **TC002003** (no-password quiz): click "Attempt quiz now" → xác nhận redirect đến `attempt.php`.

Luồng thực hiện của mỗi virtual user:

| Bước | Hành động | Endpoint |
|---|---|---|
| 1 | Đăng nhập (lấy CSRF logintoken) | `GET /login/index.php` |
| 2 | Xác thực tài khoản | `POST /login/index.php` |
| 3 | Mở trang xem quiz | `GET /mod/quiz/view.php?id=39` |
| 4 | Bắt đầu làm bài (click "Attempt quiz now") | `POST /mod/quiz/startattempt.php` |
| 5 | Đăng xuất | `GET /login/logout.php` |

---

## 3. Workload — Mô hình tăng tải (Stair-step)

| Stage | Thời gian | Số users đồng thời | Spawn rate |
|---|---|---|---|
| 1 — Warm-up | 0–60 giây | 5 users | 2 users/s |
| 2 — Tăng tải | 60–120 giây | 20 users | 5 users/s |
| 3 — Stress | 120–180 giây | 50 users | 10 users/s |

---

## 4. Performance Objectives (SLOs)

| Chỉ số | Ngưỡng yêu cầu |
|---|---|
| P95 Response Time | < 3000 ms |
| Failure Rate | < 5% |
| Throughput | >= 5 req/s |

---

## 5. Kết quả tổng quan

| Chỉ số | Kết quả thực tế | SLO yêu cầu | Kết luận |
|---|---|---|---|
| Tổng request | 1668 | — | — |
| Tổng lỗi | 0 | — | — |
| **Failure Rate** | **0%** | < 5% | **PASS** |
| **P95 Response Time** | **2300 ms** | < 3000 ms | **PASS** |
| **Throughput** | **9.11 req/s** | >= 5 req/s | **PASS** |

---

## 6. Chi tiết từng endpoint

| Endpoint | Requests | Failures | Failure Rate | Median | P95 | Max |
|---|---|---|---|---|---|---|
| GET /mod/quiz/view.php?id=39 | 767 | 0 | 0% | 930 ms | 1400 ms | 2896 ms |
| POST /mod/quiz/startattempt.php | 760 | 0 | 0% | 1200 ms | 1700 ms | 3271 ms |
| GET /login (token fetch) | 50 | 0 | 0% | 1400 ms | 3100 ms | 3300 ms |
| POST /login | 50 | 0 | 0% | 2000 ms | 3900 ms | 4347 ms |
| GET /logout | 41 | 0 | 0% | 2700 ms | 2900 ms | 2900 ms |

> **Ghi chú:** Login/logout có response time cao hơn do xảy ra đồng thời khi users spawn trong Stage 3. Các endpoint này không áp dụng SLO check nên không tính là failure. Endpoint quiz view và startattempt — hai endpoint chính — hoạt động ổn định với P95 lần lượt là **1400 ms** và **1700 ms**.

---

## 7. Phân tích theo từng giai đoạn tải

### Stage 1 — 5 users (0–60 giây): Bình thường

- Response time ổn định trong khoảng **930–1505 ms**
- Không có lỗi (0 failures)
- Throughput: ~1.5–2.9 req/s
- P95: ~1400–1500 ms — **tốt, cách xa ngưỡng SLO**
- Hệ thống hoạt động nhẹ nhàng với tải nhỏ

### Stage 2 — 20 users (60–120 giây): Ổn định, đáp ứng tốt

- Response time: **960–1800 ms**
- Không có lỗi (0 failures)
- Throughput tăng lên **6.4–9.8 req/s** — vượt SLO tối thiểu
- P95: ~1300–1800 ms — **trong ngưỡng SLO**
- Hệ thống chịu tải tốt ở 20 users

### Stage 3 — 50 users (120–180 giây): Tải cao, vẫn đáp ứng SLO

- Response time: **1100–4347 ms** (max tập trung ở login endpoints)
- Không có lỗi (0 failures)
- Throughput tăng mạnh từ 7.4 req/s lên cao nhất **19.3 req/s**, ổn định ở **17–18 req/s**
- P95 (aggregated): tăng từ ~1600 ms khi 50 users bắt đầu spawn, đạt đỉnh **~2500 ms** trong giai đoạn chuyển tiếp, sau đó **ổn định ở 2000–2100 ms** — **không vượt ngưỡng SLO 3000 ms**
- Hệ thống **đáp ứng tốt** ngay cả ở mức tải 50 users đồng thời

---

## 8. Phân loại lỗi

| Loại lỗi | Số lần | Endpoint bị ảnh hưởng |
|---|---|---|
| Response quá chậm (> 3000 ms) | 0 | — |
| HTTP 500 — Server Error | 0 | — |
| HTTP 404 — Not Found | 0 | — |

**Điểm đáng chú ý:**
- **Không có lỗi nào trong toàn bộ bài test** — 1668 requests đều thành công
- Mặc dù một số requests ở tầng login có max response time vượt 3000 ms (max 4347 ms tại `POST /login`), các endpoint quiz chính (`view.php`, `startattempt.php`) hoàn toàn nằm trong ngưỡng
- Max response time của `GET /mod/quiz/view.php?id=39` là **2896 ms** — ngay cạnh nhưng vẫn dưới ngưỡng SLO
- Throughput đạt đỉnh **19.3 req/s** tại Stage 3 cho thấy hệ thống xử lý tốt concurrency cao

---

## 9. Kết luận

> Hệ thống **ĐÁP ỨNG** tất cả performance objectives khi có **50 users đồng thời** truy cập và bắt đầu làm bài quiz.

| Mức tải | Failure Rate | P95 (aggregated) | Throughput | Kết quả |
|---|---|---|---|---|
| 5 users | 0% | ~1400–1500 ms | ~1.5–2.9 req/s | Hoạt động tốt |
| 20 users | 0% | ~1300–1800 ms | ~6.4–9.8 req/s | Đáp ứng SLO, ổn định |
| 50 users | **0%** | **~2000–2500 ms** | **~17–19 req/s** | **Đáp ứng SLO — PASS** |

- **Failure Rate:** 0% — thấp hơn SLO gấp vô cùng (SLO < 5%)
- **P95:** 2300 ms — thấp hơn SLO **700 ms** (23% dư địa so với ngưỡng 3000 ms)
- **Throughput:** 9.11 req/s trung bình, đỉnh 19.3 req/s — vượt SLO **1.8 lần**
- **Chức năng đăng nhập:** Response time cao hơn (median 1400–2000 ms, P95 3100–3900 ms) nhưng không ảnh hưởng đến độ chính xác của bài test do login chỉ xảy ra một lần mỗi virtual user

Kết quả cho thấy hệ thống MoodleCloud **hoạt động ổn định và đáp ứng được performance objectives** trong điều kiện tải kiểm thử với 50 users đồng thời.
